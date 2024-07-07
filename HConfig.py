import subprocess
import os
import shutil
import sys

GREEN_COLOR = "\033[92m"
RESET_COLOR = "\033[0m"


def copy_output_directory(src_dir, dest_dir):
    for root, dirs, files in os.walk(src_dir):
        for dir_name in dirs:
            if dir_name == "output":
                dest_path = os.path.join(dest_dir, dir_name)
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(os.path.join(root, dir_name), dest_path)


def make_SDK():
    command_make_distclean = ["make", "distclean"]
    command_make = ["make"]
    config_dir_make = "EVS_v1.1.7/SDK_v1.1.7/"
    config_dir_cp = "InitConfig"
    config_dir_check = "InitConfig/output"

    subprocess.run(command_make_distclean, cwd=config_dir_make)
    subprocess.run(command_make, cwd=config_dir_make)

    copy_output_directory(config_dir_make, config_dir_cp)

    if os.path.exists(config_dir_check):
        print(GREEN_COLOR + "output copied suss." + RESET_COLOR)
        return True
    else:
        print(GREEN_COLOR + "output copied fail." + RESET_COLOR)
        return False


def python_setup():
    command_setup = ["python", "setup.py", "build_ext", "--inplace", "--debug", "--verbose", "-j4"]
    config_dir_setup = "InitConfig"
    subfolder_path = "./InitConfig"

    parent_folder_path = "."

    subprocess.run(command_setup, cwd=config_dir_setup)

    for root, dirs, files in os.walk(subfolder_path):
        for file in files:
            if file.endswith(".so"):
                subfile_path = os.path.join(root, file)
                parent_file_path = os.path.join(parent_folder_path, file)
                if os.path.exists(parent_file_path):
                    os.remove(parent_file_path)
                shutil.copy(subfile_path, parent_folder_path)
                print(GREEN_COLOR + f"File '{file}' copied suss." + RESET_COLOR)


def main():
    if len(sys.argv) < 2:
        print(GREEN_COLOR + "Usage: python script_name.py <action>" + RESET_COLOR)
        print(GREEN_COLOR + "Available actions: make, setup" + RESET_COLOR)
        return

    action = sys.argv[1]

    if action == "make":
        if make_SDK():
            python_setup()
    elif action == "setup":
        python_setup()
    else:
        print(GREEN_COLOR + "Invalid action. Available actions: make, setup" + RESET_COLOR)


if __name__ == "__main__":
    main()