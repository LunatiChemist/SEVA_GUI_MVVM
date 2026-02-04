import os
import sys
import ast
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pyBEEP.controller import connect_to_potentiostat
from pyBEEP import __version__


# GUI Application
class GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Potentiostat driver - pyBEEP ")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Potentiostat controller
        self.controller = connect_to_potentiostat()

        # Getting the available mode from the Potentiostat
        self.mode_list = self.controller.get_available_modes()

        # Mode Combobox (scrollable list dropdown)
        self.combobox_mode_item = tk.StringVar()
        self.combobox_mode_label = tk.Label(self.root, text="Select Mode:")
        self.combobox_mode = ttk.Combobox(
            self.root,
            textvariable=self.combobox_mode_item,
            values=self.mode_list,
            state="readonly",
            width=8,
        )

        # Bind event to trigger change of plate
        self.combobox_mode.bind(
            "<<ComboboxSelected>>", lambda event: self.update_param_list()
        )

        # Run button
        self.run_button = tk.Button(
            self.root,
            text="Run Experiment",
            command=self.run_experiment,
            bg="green",
            fg="white",
        )

        # Import parameters button
        self.parameter_window_import_button = tk.Button(
            self.root,
            text="Import parameters",
            command=self.import_parameter,
            bg="gray",
            fg="white",
        )

        # Save parameters button
        self.parameter_window_save_button = tk.Button(
            self.root,
            text="Save parameters",
            command=self.save_parameter,
            bg="gray",
            fg="white",
        )

        # Optional Parameters
        self.optional_label = tk.Label(self.root, text="OPTIONAL PARAMETERS:")

        # Optional Parameters - Tia Gain
        self.tia_gain = tk.StringVar()
        self.tia_gain_label = tk.Label(self.root, text="Tia Gain (int)")
        self.tia_gain_entry = tk.Entry(self.root, width=20, textvariable=self.tia_gain)

        # Optional Parameters - Sampling Interval
        self.sampling_interval = tk.StringVar()
        self.sampling_interval_label = tk.Label(
            self.root, text="Sampling Interval (float)"
        )
        self.sampling_interval_entry = tk.Entry(
            self.root, width=20, textvariable=self.sampling_interval
        )

        # Optional Parameters - Charge Cut-off
        self.charge_cutoff = tk.StringVar()
        self.charge_cutoff_label = tk.Label(self.root, text="Charge cut-off (C):")
        self.charge_cutoff_entry = tk.Entry(
            self.root, width=20, textvariable=self.charge_cutoff
        )

        # Optional Parameters - Filename Out
        self.filename = tk.StringVar()
        self.filename_label = tk.Label(self.root, text="Output Filename")
        self.filename_entry = tk.Entry(self.root, width=20, textvariable=self.filename)

        # Optional Parameters - Folder Out
        self.folder = tk.StringVar()
        self.folder_label = tk.Label(self.root, text="Output Folder")
        self.folder_entry = tk.Entry(
            self.root, width=20, state="readonly", textvariable=self.folder
        )
        self.folder_button = tk.Button(
            self.root, text="Browse", command=self.select_folder
        )

        # Required Parameters
        self.required_label = tk.Label(self.root, text="REQUIRED PARAMETERS:")

        # Parameter File
        self.param_file_description = "Parameter File for Experiment Run with pyBEEP"

        # Required Parameters
        self.param_dict = {}
        self.mode = None
        self.param = {}
        self.parameters_list = []
        self.parameters_list_type = []
        self.parameters_values = []
        self.parameters_label = []
        self.parameters_entry = []

        self.display_initial_grid()

    def display_initial_grid(self):
        # Mode
        self.combobox_mode_label.grid(row=0, column=0, sticky="e", padx=5, pady=(15, 5))
        self.combobox_mode.grid(row=0, column=1, sticky="w", pady=(15, 5))
        # Import Parameter File
        self.parameter_window_import_button.grid(
            row=0, column=2, padx=(0, 10), pady=(15, 5)
        )

        # Optional Parameters
        self.optional_label.grid(row=1, column=0, padx=10, pady=(15, 10), sticky="e")

        # Optional Parameters - Tia Gain
        self.tia_gain_label.grid(row=2, column=0, padx=5, pady=(0, 10), sticky="e")
        self.tia_gain_entry.grid(row=2, column=1, padx=5, pady=(0, 10), sticky="w")

        # Optional Parameters - Sampling Interval
        self.sampling_interval_label.grid(
            row=3, column=0, padx=5, pady=(0, 10), sticky="e"
        )
        self.sampling_interval_entry.grid(row=3, column=1, padx=5, pady=(0, 10))

        # Optional Parameters - Charge Cut-off
        self.charge_cutoff_label.grid(row=4, column=0, padx=5, pady=(0, 10), sticky="e")
        self.charge_cutoff_entry.grid(row=4, column=1, padx=5, pady=(0, 10), sticky="w")

        # Optional Parameters - Filename Out
        self.filename_label.grid(row=5, column=0, padx=5, pady=(0, 10), sticky="e")
        self.filename_entry.grid(row=5, column=1, padx=5, pady=(0, 10), sticky="w")

        # Optional Parameters - Folder Out
        self.folder_label.grid(row=6, column=0, padx=5, pady=(0, 10), sticky="e")
        self.folder_entry.grid(row=6, column=1, padx=5, pady=(0, 10), sticky="w")
        self.folder_button.grid(row=6, column=2, padx=5, sticky="w")

    def select_folder(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.folder.set(path.replace("/", os.sep))

    def update_param_list(self):
        self.mode = self.combobox_mode_item.get()
        self.param_dict = self.controller.get_mode_params(self.mode)

        # Destruction
        for i in range(len(self.parameters_list)):
            self.parameters_label[i].grid_remove()
            self.parameters_entry[i].grid_remove()

        self.parameters_label = []
        self.parameters_entry = []
        self.parameters_list = []
        self.parameters_list_type = []
        self.parameters_values = []

        # Display
        self.required_label.grid(row=7, column=0, padx=5, pady=(15, 10), sticky="e")

        self.parameters_list = list(self.param_dict.keys())
        for i, param in enumerate(self.parameters_list):
            self.parameters_values.append(tk.StringVar())

            # Creation
            self.parameters_list_type.append(self.param_dict[param].__name__)
            label = param + " (" + self.parameters_list_type[i] + ")"
            self.parameters_label.append(tk.Label(self.root, text=label))
            self.parameters_entry.append(
                tk.Entry(self.root, width=20, textvariable=self.parameters_values[i])
            )

            # Display
            self.parameters_label[i].grid(
                row=i + 8, column=0, padx=5, pady=(0, 10), sticky="e"
            )
            self.parameters_entry[i].grid(
                row=i + 8, column=1, padx=5, pady=(0, 10), sticky="w"
            )

        # Display
        self.run_button.grid(row=len(self.parameters_list) + 8, column=1, pady=20)
        self.parameter_window_save_button.grid(
            row=len(self.parameters_list) + 8, column=2, padx=(0, 10)
        )

    def run_experiment(self):
        if self.mode is None:
            messagebox.showerror("Error", "Please select a mode")
            return

        for i, param in enumerate(self.parameters_list):
            value = self.parameters_values[i].get()
            if value == "":
                if self.parameters_list_type[i] == "Optional":
                    pass
                else:
                    messagebox.showerror("Error", "Please fill all the parameters")
                    return
            if self.parameters_list_type[i] == "float":
                self.param[param] = float(value)
            elif self.parameters_list_type[i] == "int":
                self.param[param] = int(float(value))
            elif self.parameters_list_type[i] == "List":
                lst = [float(x.strip()) for x in value.split(",")]
                if not isinstance(lst, list):
                    messagebox.showerror("Error", f"{param} (List): {lst}, is not a List Type")
                    return
                self.param[param] = lst
            elif self.parameters_list_type[i] == "Optional":
                if value == "":
                    self.param[param] = None
                else:
                    self.param[param] = float(value)
            else:
                raise TypeError(
                    f"Unknown parameter type: {self.parameters_list_type[i]}"
                )

        if self.tia_gain.get() == "":
            tia_gain = 0
        else:
            tia_gain = int(float(self.tia_gain.get()))
        if self.sampling_interval.get() == "":
            sampling_interval = None
        else:
            sampling_interval = float(self.sampling_interval.get())
        if self.filename.get() == "":
            filename = None
        else:
            filename = self.filename.get()
        if self.folder.get() == "":
            folder = None
        else:
            folder = self.folder.get()
        if self.charge_cutoff.get() == "":
            charge_cutoff_c = None
        else:
            charge_cutoff_c = float(self.charge_cutoff.get())

        self.controller.apply_measurement(
            self.mode,
            self.param,
            tia_gain=tia_gain,
            sampling_interval=sampling_interval,
            filename=filename,
            folder=folder,
            charge_cutoff_c=charge_cutoff_c,
        )

    def import_parameter(self):
        path_open = filedialog.askopenfilename(title="Select Parameter File")

        if path_open:
            with open(path_open, "r") as f:
                line = f.readline()
                if (self.param_file_description in line) and (__version__ in line):
                    f.readline()
                    line = f.readline()
                    line = line.removesuffix("\n")
                    self.mode = line.split(" : ")[1]
                    self.combobox_mode_item.set(self.mode)
                    self.update_param_list()
                    f.readline()
                    for i in range(len(self.parameters_list)):
                        line = f.readline()
                        line = line.removesuffix("\n")
                        self.parameters_values[i].set(line.split(" = ")[1])

                    f.readline()
                    line = f.readline()
                    line = line.removesuffix("\n")
                    self.tia_gain.set(line.split(" = ")[1])

                    line = f.readline()
                    line = line.removesuffix("\n")
                    self.sampling_interval.set(line.split(" = ")[1])

                    line = f.readline()
                    line = line.removesuffix("\n")
                    self.filename.set(line.split(" = ")[1])

                    line = f.readline()
                    line = line.removesuffix("\n")
                    self.folder.set(line.split(" = ")[1])

                else:
                    print("WARNING: Not compatible Parameter File")

    def save_parameter(self):
        path_save = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            title="Save your Parameter File as...",
        )

        if path_save:
            with open(path_save, "w") as f:
                f.write(f"{self.param_file_description} - {__version__}\n\n")
                f.write(f"Mode : {self.mode}\n\n")
                for i in range(len(self.parameters_list)):
                    label = (
                        self.parameters_list[i]
                        + " ("
                        + self.parameters_list_type[i]
                        + ")"
                    )
                    f.write(f"{label} = {self.parameters_values[i].get()}\n")

                f.write(f"\nTia Gain (int) = {self.tia_gain.get()}\n")
                f.write(f"Sampling Interval (float) = {self.sampling_interval.get()}\n")
                f.write(f"Output Filename = {self.filename.get()}\n")
                f.write(f"Output Folder = {self.folder.get()}\n")

            print("Parameters saved to " + path_save)

        else:
            print("Parameters saving canceled")

    def on_close(self):
        self.root.destroy()
        sys.exit()


def launch_GUI():
    root = tk.Tk()
    GUI(root)
    root.mainloop()


# Run the app
if __name__ == "__main__":
    launch_GUI()
