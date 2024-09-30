# Cài đặt môi trường
## Install GPU driver
    `sudo apt-get update
    sudo apt-get upgrade
    sudo ubuntu-drivers [select version driver]
    sudo reboot`

## Check version, install gcc, cuda, cudnn.
    `Ubuntu: lsb_release -a
    Cuda: nvcc -V
    Cudnn: ls /usr/local/cuda/lib64/libcudnn*
    gcc -v
    (We will need to install the gcc compiler as it will be used when installing the CUDA toolkit.)
            can ref: https://github.com/Vuong02011996/tools_ubuntu/blob/master/install.sh`


## Setup và chạy project
    Pycharm
    Cài anaconda
    https://docs.anaconda.com/free/anaconda/install/linux/
    Download project - zip or git
    Tạo môi trường conda 
    install requirements.txt

# Chạy chương trình test video hoặc camera.
    Copy .env_copy ->.env
    Run server.py

