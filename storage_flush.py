import os
import shutil
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path


class StorageFlusher:
    def __init__(
        self,
        staging_dir:    str,
        bucket_name:    str   = "",
        prefix:         str   = "scan_results",
        threshold_gb:   float = 50.0,
        zip_output_dir: str   = "",
        dry_run:        bool  = False,
    ):
        self.staging_dir     = staging_dir
        self.bucket_name     = bucket_name or os.environ.get("STORAGE_BUCKET", "")
        self.prefix          = prefix or os.environ.get("STORAGE_PREFIX", "scan_results")
        self.threshold_bytes = int(threshold_gb * 1024 ** 3)  # Convert GB threshold to bytes for direct size comparisons
        self.zip_output_dir  = zip_output_dir or str(
            Path(staging_dir).resolve().parent / "zips"
        )
       
        self.dry_run         = dry_run  # dry_run=True, this allow me to actually test the flush logic without touching GCS

        self._flush_count          = 0
        self._total_uploaded_bytes = 0
        self._total_zipped_bytes   = 0

        self._gcs_client           = None
        self._gcs_bucket           = None
        self._flush_timings        = []
        self._flush_zip_names      = []
        self._lock                 = threading.Lock()  # makes sure only one flush runs at a time

        os.makedirs(staging_dir, exist_ok=True)
        os.makedirs(self.zip_output_dir, exist_ok=True)

    # Size tracking - Walk the staging directory and return total size in bytes.
    def get_staging_size(self) -> int:
        total = 0
        for root, _dirs, files in os.walk(self.staging_dir):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total

    # def get_staging_size_gb(self) -> float:
    #     return self.get_staging_size() / (1024 ** 3)

    def get_staging_file_count(self) -> int:
        count = 0
        for _, _, files in os.walk(self.staging_dir):
            count += len(files)
        return count

    # Flush triggers
    def check_and_flush(self) -> bool:
        current_size = self.get_staging_size()
        if current_size < self.threshold_bytes:
            return False
        gb = current_size / (1024 ** 3)
        print(f"\n  Staging ({gb:.1f} GB, {self.get_staging_file_count()} files) "
              f"exceeds {self.threshold_bytes / (1024 ** 3):.0f} GB - flushing...")
        return self.do_flush()

    def check_and_flush_before(self, incoming_bytes: int) -> bool:
        if incoming_bytes <= 0:
            return False
        current_size   = self.get_staging_size()
        projected_size = current_size + incoming_bytes
        if projected_size < self.threshold_bytes:
            return False
        print(f"\n  Pre-emptive flush: {current_size / (1024**3):.1f} GB staging + "
              f"~{incoming_bytes / (1024**3):.1f} GB incoming would exceed threshold - flushing now...")
        return self.do_flush()

    def force_flush(self) -> bool:
        the_current_staging_size = self.get_staging_size()
        if the_current_staging_size == 0:
            print("  Staging is empty - nothing to flush.")
            return False
        print(f"\n  Force flushing staging ({the_current_staging_size / (1024**3):.2f} GB, "
              f"{self.get_staging_file_count()} files)...")
        return self.do_flush()

    # Core: atomic rename -> zip snapshot -> upload -> verify -> delete snapshot
    def do_flush(self) -> bool:
        with self._lock:
            timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_dir = self.staging_dir.rstrip("/\\") + f"_snap_{timestamp}"
            zip_name    = f"scan_flagged_{timestamp}_batch{self._flush_count + 1}.zip"
            zip_path    = os.path.join(self.zip_output_dir, zip_name)

            # Step 1 - Atomic rename: workers immediately get a fresh empty staging dir
            try:
                os.rename(self.staging_dir, snapshot_dir)
                os.makedirs(self.staging_dir, exist_ok=True)
            except Exception as e:
                print(f"  Atomic rename failed: {e}")
                return False

            # Step 2 - Zip the snapshot (workers write freely to fresh staging_dir)
            # Pre-check: if there isn't enough free disk to hold the zip, skip archiving
            # and just delete the snapshot to free space so that run can continue.
            try:
                free_bytes = shutil.disk_usage(self.staging_dir).free
            except Exception:
                free_bytes = shutil.disk_usage(".").free
            snapshot_size = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _, files in os.walk(snapshot_dir)
                for f in files
            )
            if free_bytes < snapshot_size + 2 * 1024 ** 3:  # need snapshot_size + 2 GB headroom
                print(f"  Not enough space to zip ({free_bytes / (1024**3):.1f} GB free, "
                      f"need {(snapshot_size + 2 * 1024**3) / (1024**3):.1f} GB) -- "
                      f"deleting snapshot to free {snapshot_size / (1024**3):.1f} GB")
                shutil.rmtree(snapshot_dir, ignore_errors=True)
                return False

            print(f"  Zipping snapshot -> {zip_name}")
            file_count    = 0
            original_size = 0
            t_zip_start   = time.monotonic()
            try:
                # ML model files are already compressed binaries -- STORED is pure disk I/O
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                    for root, _dirs, files in os.walk(snapshot_dir):
                        for fname in files:
                            if fname == "flagged_log.jsonl":
                                continue  # excluded -- data is in .verdicts.json and the DB
                            local_path = os.path.join(root, fname)
                            arc_name   = os.path.relpath(local_path, snapshot_dir)
                            try:
                                original_size += os.path.getsize(local_path)
                                zf.write(local_path, arcname=arc_name)
                                file_count += 1
                            except OSError as e:
                                print(f"    Skipped {arc_name}: {e}")
            except Exception as e:
                print(f"  Zip failed: {e}")
                shutil.rmtree(snapshot_dir, ignore_errors=True)
                try:
                    os.remove(zip_path)
                except OSError:
                    pass
                return False
            t_zip = time.monotonic() - t_zip_start

            zip_size = os.path.getsize(zip_path)
            print(f"  Zipped {file_count} files in {t_zip:.1f}s: "
                  f"{original_size / (1024**3):.2f} GB -> {zip_size / (1024**3):.2f} GB")
            self._total_zipped_bytes += zip_size

            # Step 2.5 - Delete snapshot now that it's safely in the zip.
            shutil.rmtree(snapshot_dir, ignore_errors=True)

            if self.dry_run:
                print(f"  DRY RUN - would upload {zip_name} to "
                      f"gs://{self.bucket_name}/{self.prefix}/")
                return True

            # Step 3 - Upload
            # using upload_parallel() -- gsutil parallel composite, 4-8x faster than single stream
            # to revert: change upload_parallel back to upload and uncomment the old upload() method above
            t_upload_start = time.monotonic()
            if not self.upload_parallel(zip_path, zip_name):
                print("  Upload failed - zip kept locally as backup, snapshot freed")
                return False
            t_upload = time.monotonic() - t_upload_start

            # Step 4 - Verify
            t_verify_start = time.monotonic()
            if not self.verify(zip_name, zip_size):
                print("  Verification failed - zip kept locally as backup, snapshot freed")
                return False
            t_verify = time.monotonic() - t_verify_start

            self._total_uploaded_bytes += zip_size

            # Step 5 - Delete local zip now that GCS upload is confirmed
            try:
                os.remove(zip_path)
                print("  Deleted local zip after upload")
            except OSError:
                pass

            t_total = t_zip + t_upload + t_verify
            self._flush_count += 1
            self._flush_zip_names.append(zip_name)
            self._flush_timings.append({
                "batch":      self._flush_count,
                "zip_name":   zip_name,
                "zip_s":      round(t_zip,    1),
                "upload_s":   round(t_upload,  1),
                "verify_s":   round(t_verify,  1),
                "total_s":    round(t_total,   1),
                "files":      file_count,
                "size_gb":    round(zip_size / (1024**3), 2),
            })
            print(f"  Flush #{self._flush_count} complete in {t_total:.1f}s "
                  f"(zip {t_zip:.1f}s / upload {t_upload:.1f}s / verify {t_verify:.1f}s) -- "
                  f"{file_count} files "
                  f"(total uploaded: {self._total_uploaded_bytes / (1024**3):.2f} GB)")
            return True

    def cleanup_local_zips(self) -> int:
        """Delete all local zip files. Returns bytes freed."""
        freed = 0
        if not os.path.isdir(self.zip_output_dir):
            return 0
        for fname in os.listdir(self.zip_output_dir):
            if fname.endswith(".zip"):
                fpath = os.path.join(self.zip_output_dir, fname)
                try:
                    freed += os.path.getsize(fpath)
                    os.remove(fpath)
                    print(f"  Deleted local zip: {fname}")
                except OSError:
                    pass
        return freed

    # GCS
    def connect(self) -> bool:
        if self._gcs_client is not None:
            return True
        if not self.bucket_name:
            print("  STORAGE_BUCKET not set")
            return False
        try:
            from google.cloud import storage
            gcs_project      = os.environ.get("GCS_PROJECT")
            self._gcs_client = storage.Client(project=gcs_project)
            self._gcs_bucket = self._gcs_client.bucket(self.bucket_name)
            print(f"  Connected to GCS: gs://{self.bucket_name}")
            return True
        except ImportError:
            print("  google-cloud-storage not installed - pip install google-cloud-storage")
            return False
        except Exception as e:
            print(f"  GCS connection failed: {e}")
            return False

    def upload_parallel(self, zip_path: str, zip_name: str) -> bool:
        import subprocess
        gcs_key = f"gs://{self.bucket_name}/{self.prefix}/{zip_name}"
        print(f"  Uploading (parallel composite) -> {gcs_key}")
        try:
            result = subprocess.run(
                [
                    "gsutil",
                    # parallel composite -- splits file into chunks, uploads simultaneously
                    "-o", "GSUtil:parallel_composite_upload_threshold=150M",
                    # each chunk is 200mb -- 30gb zip = ~150 parallel chunks
                    "-o", "GSUtil:parallel_composite_upload_component_size=200M",
                    "cp",
                    zip_path,
                    gcs_key,
                ],
                capture_output=True,
                text=True,
                timeout=1800,   # 30 min timeout - uploading large zips can be slow, and I don't want to kill the whole pipeline if it takes a while
            )
            if result.returncode != 0:
                print(f"  gsutil upload failed (exit {result.returncode}): {result.stderr[:300]}")
                return False
            print(f"  Uploaded")
            return True
        except FileNotFoundError:
            print("  gsutil not found -- is google-cloud-sdk installed?")
            return False
        except subprocess.TimeoutExpired:
            print("  gsutil upload timed out after 30 min")
            return False
        except Exception as e:
            print(f"  Upload failed: {e}")
            return False

    def  verify(self, zip_name: str, expected_size: int) -> bool:
        """Confirm object exists in GCS and size matches before deleting staging."""
        try:
            blob = self._gcs_bucket.blob(f"{self.prefix}/{zip_name}")
            blob.reload()
            if blob.size != expected_size:
                print(f"  Size mismatch: expected {expected_size}, got {blob.size}")
                return False
            print(f"  Verified: {zip_name} ({blob.size / (1024**3):.2f} GB)")
            return True
        except Exception as e:
            print(f"  Verification failed: {e}")
            return False

    # Shows the Stats
    def stats(self) -> dict:
        return {
            "bucket":             self.bucket_name,
            "prefix":             self.prefix,
            "flush_count":        self._flush_count,
            "total_uploaded_gb":  self._total_uploaded_bytes / (1024 ** 3),
            "total_zipped_gb":    self._total_zipped_bytes / (1024 ** 3),
            "staging_current_gb": self.get_staging_size() / (1024 ** 3),
            "staging_file_count": self.get_staging_file_count(),
            "flush_zip_names":    self._flush_zip_names,
            "flush_timings":      self._flush_timings,
        }
