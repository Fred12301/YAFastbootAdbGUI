import os
import sys
import subprocess
import zipfile
from zipfile import ZipFile
from posixpath import expanduser
import winreg
import easygui
import dearpygui.dearpygui as dpg

# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------

def log_text(log_window: str, message: str) -> None:
    """
    Logs a message to the DearPyGui widget specified by log_window.
    (Keep it simple: just text with automatic scrolling.)
    """
    dpg.add_text(message, parent=log_window)
    dpg.set_y_scroll(log_window, 999999)  # Always scroll to the bottom

def execute_command(command: list, log_window: str, timeout: int = 10, alternatives: list = None) -> int:
    """
    Executes a command using subprocess and logs stdout and stderr.
    In case of a timeout, it optionally tries a list of alternative commands.
    
    :param command: The main command as a list of strings.
    :param log_window: The log widget where output will be displayed.
    :param timeout: Maximum time in seconds.
    :param alternatives: List of alternative commands (if needed).
    :return: The return code of the main command (or None in case of failure).
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        for line in result.stdout.strip().splitlines():
            log_text(log_window, line)
        for line in result.stderr.strip().splitlines():
            log_text(log_window, line)
        return result.returncode
    except subprocess.TimeoutExpired:
        log_text(log_window, f"Command {' '.join(command)} timed out.")
        if alternatives:
            for alt in alternatives:
                try:
                    log_text(log_window, f"Trying alternative: {' '.join(alt)}")
                    alt_result = subprocess.run(alt, capture_output=True, text=True, timeout=timeout)
                    for line in alt_result.stdout.strip().splitlines():
                        log_text(log_window, line)
                    for line in alt_result.stderr.strip().splitlines():
                        log_text(log_window, line)
                except subprocess.TimeoutExpired:
                    log_text(log_window, f"Alternative {' '.join(alt)} also timed out.")
        return None

# ------------------------------------------------------------------------------
# Device Management (ADB / Fastboot)
# ------------------------------------------------------------------------------

class DeviceManager:
    def __init__(self, log_window: str):
        self.log_window = log_window

    def reboot(self, mode: str, is_fastboot: bool) -> None:
        """
        Reboots the device in a given mode.
        
        :param mode: 'Normal', 'Recovery', 'Fastboot' or 'EDL'
        :param is_fastboot: True to use fastboot, False to use adb.
        """
        base_cmd = "fastboot" if is_fastboot else "adb"
        mode_lower = mode.lower()
        if not is_fastboot:
            if mode_lower == "normal":
                cmd = [base_cmd, "reboot"]
            elif mode_lower == "recovery":
                cmd = [base_cmd, "reboot", "recovery"]
            elif mode_lower == "fastboot":
                cmd = [base_cmd, "reboot", "bootloader"]
            elif mode_lower == "edl":
                cmd = [base_cmd, "reboot", "edl"]
            else:
                log_text(self.log_window, f"Unknown mode for adb reboot: {mode}")
                return
        else:
            if mode_lower == "normal":
                cmd = [base_cmd, "reboot"]
            elif mode_lower == "recovery":
                cmd = [base_cmd, "reboot", "recovery"]
            elif mode_lower == "fastboot":
                cmd = [base_cmd, "reboot-bootloader"]
            elif mode_lower == "edl":
                cmd = [base_cmd, "reboot", "edl"]
            else:
                log_text(self.log_window, f"Unknown mode for fastboot reboot: {mode}")
                return

        log_text(self.log_window, f"Executing command: {' '.join(cmd)}")
        execute_command(cmd, self.log_window)

    def flash(self, file_path: str, partition: str) -> None:
        """
        Flashes the specified partition with the given file.
        
        :param file_path: Path to the file to flash.
        :param partition: Name of the partition (will be converted to lowercase).
        """
        partition_lower = partition.lower()
        log_text(self.log_window, f"Flashing partition {partition_lower} with file {file_path}...")
        cmd = ["fastboot", "flash", partition_lower, file_path]
        if execute_command(cmd, self.log_window) is not None:
            log_text(self.log_window, f"Successfully flashed partition {partition_lower}!")
        else:
            log_text(self.log_window, f"Failed to flash partition {partition_lower}.")

    def unlock_bootloader(self) -> None:
        """
        Attempts to unlock the bootloader by trying two methods.
        """
        dpg.delete_item(self.log_window, children_only=True)
        log_text(self.log_window, "Attempting to unlock the bootloader...")
        cmd_primary = ["fastboot", "flashing", "unlock"]
        cmd_alternative = ["fastboot", "oem", "unlock"]
        if execute_command(cmd_primary, self.log_window, alternatives=[cmd_alternative]) is None:
            log_text(self.log_window, "Unable to unlock the bootloader with the provided commands.")

    def lock_bootloader(self) -> None:
        """
        Attempts to lock the bootloader by trying two methods.
        """
        dpg.delete_item(self.log_window, children_only=True)
        log_text(self.log_window, "Attempting to lock the bootloader...")
        cmd_primary = ["fastboot", "flashing", "lock"]
        cmd_alternative = ["fastboot", "oem", "lock"]
        if execute_command(cmd_primary, self.log_window, alternatives=[cmd_alternative]) is None:
            log_text(self.log_window, "Failed to lock the bootloader with the provided commands.")

    def get_info(self, info_type: str) -> None:
        """
        Retrieves device information (state or serial number).
        
        :param info_type: 'state' or 'sn'
        """
        info_type_lower = info_type.lower()
        if info_type_lower == "state":
            cmd = ["adb", "get-state", "device"]
        elif info_type_lower == "sn":
            cmd = ["adb", "get-serialno"]
        else:
            log_text(self.log_window, f"Unknown info type: {info_type}")
            return
        dpg.delete_item(self.log_window, children_only=True)
        execute_command(cmd, self.log_window)

    def restart_adb_server(self) -> None:
        """
        Restarts the ADB server.
        """
        dpg.delete_item(self.log_window, children_only=True)
        log_text(self.log_window, "Restarting ADB server...")
        execute_command(["adb", "kill-server"], self.log_window)
        execute_command(["adb", "start-server"], self.log_window)

    def get_devices(self) -> None:
        """
        Displays the list of devices connected via adb and fastboot.
        """
        dpg.delete_item(self.log_window, children_only=True)
        log_text(self.log_window, "Retrieving list of connected devices...")
        execute_command(["adb", "devices"], self.log_window)
        execute_command(["fastboot", "devices"], self.log_window)

# ------------------------------------------------------------------------------
# Installation and PATH Configuration
# ------------------------------------------------------------------------------

class Installer:
    """
    Manages the installation of tools (extracting archives and adding platform-tools to the PATH).
    """
    def __init__(self, log_window: str):
        self.log_window = log_window

    def add_to_path(self, zipname: str) -> None:
        """
        Extracts the zip archive and adds the platform-tools folder to the PATH.
        
        :param zipname: Name of the zip file containing platform-tools.
        """
        try:
            with ZipFile(zipname, 'r') as zip_ref:
                zip_ref.extractall("platform-tools")
            log_text(self.log_window, "Successfully extracted platform-tools.")
        except Exception as e:
            log_text(self.log_window, f"Error extracting {zipname}: {e}")
            return

        if os.name == "nt":
            self._install_windows()
        elif os.name == "posix":
            self._install_linux()
        else:
            log_text(self.log_window, "OS not supported for automatic installation.")

    def _install_windows(self) -> None:
        try:
            adb_folder = os.path.expandvars(r"%userprofile%\adb")
            with ZipFile("win.zip", 'r') as zip_ref:
                zip_ref.extractall(adb_folder)
            os.remove("win.zip")
            log_text(self.log_window, "Successfully extracted Windows ADB files.")
            # Modify the PATH in the registry
            path_to_modify = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path_to_modify, 0, winreg.KEY_ALL_ACCESS)
            current_path = winreg.QueryValueEx(key, "Path")[0]
            new_path = os.path.join(adb_folder, "platform-tools")
            modified_path = current_path + ";" + new_path
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, modified_path)
            winreg.CloseKey(key)
            log_text(self.log_window, "PATH modification completed. Please restart the program.")
            easygui.msgbox(msg="Installation complete. Please restart the program!", title="Installation Complete")
            sys.exit(0)
        except Exception as e:
            log_text(self.log_window, f"Error during Windows installation: {e}")

    def _install_linux(self) -> None:
        try:
            # Correct import: ZipFile is already imported from zipfile
            with ZipFile("linux.zip", 'r') as zip_ref:
                zip_ref.extractall(expanduser("~"))
            os.remove("linux.zip")
            log_text(self.log_window, "Successfully extracted platform-tools for Linux.")
            shell = os.readlink(f'/proc/{os.getppid()}/exe')
            shell_name = shell[shell.rfind('/')+1:]
            log_text(self.log_window, f"Detected shell: {shell_name}")
            rc_file = ""
            export_line = ""
            if shell_name.endswith("bash"):
                rc_file = os.path.join(expanduser("~"), ".bashrc")
                export_line = "export PATH=$PATH:~/platform-tools"
            elif shell_name.endswith("zsh"):
                rc_file = os.path.join(expanduser("~"), ".zshrc")
                export_line = 'export PATH="$PATH:~/platform-tools"'
            elif shell_name.endswith("fish"):
                rc_file = os.path.join(expanduser("~"), ".config", "fish", "config.fish")
                export_line = "set PATH $PATH ~/platform-tools"
            else:
                log_text(self.log_window, "Shell not supported for automatic PATH addition.")
                return

            with open(rc_file, "r") as f:
                content = f.read()
            if "platform-tools" not in content:
                with open(rc_file, "a") as f:
                    f.write("\n" + export_line + "\n")
                log_text(self.log_window, f"Added the following line to {rc_file}: {export_line}")
                os.system(f'source {rc_file}')  # Note: this command does not affect the parent shell's environment.
            else:
                log_text(self.log_window, "platform-tools is already present in the PATH.")
            os.system('chmod +x ~/platform-tools/*')
            if os.system('groups | grep -q plugdev') == 0:
                log_text(self.log_window, "Installation complete. Please restart the program!")
                easygui.msgbox(title="Installation Complete", msg="Please restart the program!")
            else:
                log_text(self.log_window, "User is not a member of the plugdev group, addition required (sudo needed).")
                os.system('sudo usermod -a -G plugdev $USER')
                log_text(self.log_window, "Group addition done. Please log out/in again.")
        except Exception as e:
            log_text(self.log_window, f"Error during Linux installation: {e}")

# ------------------------------------------------------------------------------
# Example Usage
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # DearPyGui configuration
    dpg.create_context()
    with dpg.window(label="Log", tag="log_window", width=600, height=400):
        pass
    dpg.create_viewport(title='Device Manager', width=600, height=400)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    # Retrieve the log widget by its tag
    log_window = "log_window"

    # Instantiate the device manager
    device_manager = DeviceManager(log_window)
    # Example: reboot into Recovery mode (using adb)
    # device_manager.reboot("Recovery", is_fastboot=False)
    # Example: display connected devices
    # device_manager.get_devices()

    # Instantiate the installer and add platform-tools to the PATH
    # installer = Installer(log_window)
    # installer.add_to_path("platform-tools.zip")
    
    # Start the GUI event loop
    dpg.start_dearpygui()
    dpg.destroy_context()
