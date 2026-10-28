from huggingface_hub import get_paths_info
paths_info = get_paths_info("poolside/Laguna-XS.2", ["model-00001-of-00014.safetensors", "en"], repo_type="model", expand=True)
# print("Length:", len(paths_info))

print (paths_info)

