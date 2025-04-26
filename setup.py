import os

def install_common_libs():
    os.system("pip install transformers==4.40.1 peft==0.10.0 trl==0.8.6 bitsandbytes==0.43.0 accelerate==0.29.3")
    os.system("pip install einops scipy")
    
if __name__ == "__main__":
    install_common_libs()
