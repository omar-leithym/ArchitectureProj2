from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import backend as backend
import ExecutionUnit as ExecutionUnit

# Initialize the main application window
root = Tk()
root.title("Tomasulo Simulator")
root.geometry("1000x900")  # Increased size to accommodate the table and config
root.configure(bg="#f0f0f0")

# Label for the app title
titleLabel = Label(root, text="Tomasulo Simulator", font=("Helvetica", 16, "bold"), bg="#f0f0f0")
titleLabel.grid(row=0, column=0, columnspan=3, pady=(10, 20), sticky="w", padx=(20, 0))

# Label for syntax instructions
syntaxText = """This is a simulator that simulates the instructions using Tomasulo's algorithm without speculation.

The supported instructions are:
1. Load/Store:
   - LOAD rA, offset(rB)
   - STORE rA, offset(rB)
   
2. Conditional Branch:
   - BEQ rA, rB, offset
   
3. Call/Return:
   - CALL label
   - RET
   
4. Arithmetic and Logic:
   - ADD rA, rB, rC
   - SUB rA, rB, rC
   - NOR rA, rB, rC
   - MUL rA, rB, rC

Registers: r0 to r7 (r0 is always 0)
"""

syntaxLabel = Label(root, text=syntaxText, font=("Helvetica", 10), justify="left", anchor="nw", bg="#f0f0f0", wraplength=300)
syntaxLabel.grid(row=1, column=0, padx=(20, 10), sticky="nw")

# Frame to hold the instructions Text box and scrollbar
instructions_frame = Frame(root)
instructions_frame.grid(row=1, column=1, padx=(10, 5), pady=(10, 0), sticky="nsew")

# Label for Instructions Text box
instructionsLabel = Label(instructions_frame, text="Instructions", font=("Helvetica", 12, "bold"), bg="#f0f0f0")
instructionsLabel.pack(anchor="w")

# Instructions Text box
instructionsBox = Text(instructions_frame, height=20, width=35, font=("Courier", 10), wrap="word")
instructionsBox.pack(side="left", fill="both", expand=True)
instructionsScrollbar = Scrollbar(instructions_frame, command=instructionsBox.yview)
instructionsScrollbar.pack(side="right", fill="y")
instructionsBox.config(yscrollcommand=instructionsScrollbar.set)

# Frame to hold the memory Text box
memory_frame = Frame(root)
memory_frame.grid(row=1, column=2, padx=(5, 20), pady=(10, 0), sticky="nsew")

# Label for Memory Text box
memoryLabel = Label(memory_frame, text="Memory", font=("Helvetica", 12, "bold"), bg="#f0f0f0")
memoryLabel.pack(anchor="w")

memoryBox = Text(memory_frame, height=15, width=35, font=("Courier", 10), wrap="word")
memoryBox.pack(side="left", fill="both", expand=True)
memoryScrollbar = Scrollbar(memory_frame, command=memoryBox.yview)
memoryScrollbar.pack(side="right", fill="y")
memoryBox.config(yscrollcommand=memoryScrollbar.set)

# PC Frame
pc_frame = Frame(root, bg="#f0f0f0")
pc_frame.grid(row=2, column=0, padx=(5, 20), pady=(10, 10), sticky="nw")

# Label for Program Counter
pc_label = Label(pc_frame, text="Initial PC", font=("Helvetica", 12, "bold"), bg="#f0f0f0")
pc_label.pack(anchor="w")

pc_value = IntVar(value=0)
pc_entry = Entry(pc_frame, textvariable=pc_value, font=("Courier", 12), width=10)
pc_entry.pack(side="left", padx=(0, 10))

# Increment and Decrement Buttons
def increment_pc():
    pc_value.set(pc_value.get() + 1)  # Increment by 1

def decrement_pc():
    pc_value.set(pc_value.get() - 1)

increment_button = Button(pc_frame, text="↑", font=("Helvetica", 10), command=increment_pc, width=2)
increment_button.pack(side="left")

decrement_button = Button(pc_frame, text="↓", font=("Helvetica", 10), command=decrement_pc, width=2)
decrement_button.pack(side="left")

# Frame for functional unit configuration
fu_config_frame = Frame(root, bg="#f0f0f0")
fu_config_frame.grid(row=3, column=0, columnspan=3, padx=(20, 20), pady=(10, 10), sticky="nsew")

fu_config_label = Label(fu_config_frame, text="Functional Unit Configuration", font=("Helvetica", 12, "bold"), bg="#f0f0f0")
fu_config_label.grid(row=0, column=0, columnspan=7, sticky="w", pady=(0, 10))

# Create labels and entry fields for each functional unit type
fu_types = ["LOAD", "STORE", "ADD_SUB", "MUL", "NOR", "BEQ", "CALL_RET"]
fu_entries = {}

# Column headers
Label(fu_config_frame, text="Unit Type", font=("Helvetica", 10, "bold"), bg="#f0f0f0").grid(row=1, column=0, padx=5, pady=5)
Label(fu_config_frame, text="Cycles", font=("Helvetica", 10, "bold"), bg="#f0f0f0").grid(row=1, column=1, padx=5, pady=5)
Label(fu_config_frame, text="Count", font=("Helvetica", 10, "bold"), bg="#f0f0f0").grid(row=1, column=2, padx=5, pady=5)

# Default values for cycles and counts
default_cycles = {"LOAD": 6, "STORE": 6, "ADD_SUB": 2, "MUL": 10, "NOR": 1, "BEQ": 1, "CALL_RET": 1}
default_counts = {"LOAD": 2, "STORE": 2, "ADD_SUB": 4, "MUL": 2, "NOR": 2, "BEQ": 2, "CALL_RET": 1}

for i, fu_type in enumerate(fu_types):
    # Unit type label
    Label(fu_config_frame, text=fu_type, bg="#f0f0f0").grid(row=i+2, column=0, padx=5, pady=2, sticky="w")
    
    # Cycles entry
    cycles_var = IntVar(value=default_cycles[fu_type])
    cycles_entry = Entry(fu_config_frame, textvariable=cycles_var, width=5)
    cycles_entry.grid(row=i+2, column=1, padx=5, pady=2)
    
    # Count entry
    count_var = IntVar(value=default_counts[fu_type])
    count_entry = Entry(fu_config_frame, textvariable=count_var, width=5)
    count_entry.grid(row=i+2, column=2, padx=5, pady=2)
    
    # Store references to the variables
    fu_entries[fu_type] = {"cycles": cycles_var, "count": count_var}

# Frame to hold the output Text box and table
output_frame = Frame(root)
output_frame.grid(row=4, column=0, columnspan=3, padx=(20, 20), pady=(10, 20), sticky="nsew")

# Create a Notebook (tabbed interface)
notebook = ttk.Notebook(output_frame)
notebook.pack(fill="both", expand=True)

# Tab for simulation output
output_tab = Frame(notebook)
notebook.add(output_tab, text="Simulation Output")

outputLabel = Label(output_tab, text="Simulation Output", font=("Helvetica", 12, "bold"), bg="#f0f0f0")
outputLabel.pack(anchor="w")

outputBox = Text(output_tab, height=10, width=80, font=("Courier", 10), wrap="word")
outputBox.pack(side="top", fill="both", expand=True)
outputScrollbar = Scrollbar(output_tab, command=outputBox.yview)
outputScrollbar.pack(side="right", fill="y")
outputBox.config(yscrollcommand=outputScrollbar.set)

# Tab for instruction timeline
timeline_tab = Frame(notebook)
notebook.add(timeline_tab, text="Log Table")

# Create a frame for the table
table_frame = Frame(timeline_tab)
table_frame.pack(fill="both", expand=True, padx=5, pady=5)

# Create a treeview widget for the table
columns = ("Instruction", "Issue Cycle", "Execute Start", "Execute End", "Write Cycle")
timeline_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

# Define column headings
for col in columns:
    timeline_table.heading(col, text=col)
    timeline_table.column(col, width=150, anchor="center")

# Add scrollbar
scrollbar = Scrollbar(table_frame, orient="vertical", command=timeline_table.yview)
scrollbar.pack(side="right", fill="y")
timeline_table.configure(yscrollcommand=scrollbar.set)
timeline_table.pack(fill="both", expand=True)

# Add a new tab for reservation stations
rs_tab = Frame(notebook)
notebook.add(rs_tab, text="Reservation Stations")

# Create a frame for the reservation stations table
rs_frame = Frame(rs_tab)
rs_frame.pack(fill="both", expand=True, padx=5, pady=5)

# Create a treeview widget for the reservation stations
rs_columns = ("Unit Type", "Station #", "Busy", "Op", "Vj", "Vk", "Qj", "Qk", "Dest")
rs_table = ttk.Treeview(rs_frame, columns=rs_columns, show="headings", height=15)

# Define column headings
for col in rs_columns:
    rs_table.heading(col, text=col)
    rs_table.column(col, width=80, anchor="center")

# Add scrollbar
rs_scrollbar = Scrollbar(rs_frame, orient="vertical", command=rs_table.yview)
rs_scrollbar.pack(side="right", fill="y")
rs_table.configure(yscrollcommand=rs_scrollbar.set)
rs_table.pack(fill="both", expand=True)

# Configure row weight for output frame
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)
root.grid_rowconfigure(4, weight=2)

# Add CDB status display
cdb_frame = Frame(output_frame)
cdb_frame.pack(fill="x", expand=False, padx=5, pady=5, before=notebook)

cdb_label = Label(cdb_frame, text="Common Data Bus:", font=("Helvetica", 10, "bold"))
cdb_label.pack(side="left", padx=(0, 10))

cdb_status = StringVar(value="Idle")
cdb_status_label = Label(cdb_frame, textvariable=cdb_status, font=("Helvetica", 10))
cdb_status_label.pack(side="left")

def update_rs_table(rs_data):
    # Clear existing data
    for item in rs_table.get_children():
        rs_table.delete(item)
    
    # Insert new data
    for fu_type, stations in rs_data.items():
        for i, rs in enumerate(stations):
            values = [
                fu_type,
                i,
                "Yes" if rs['busy'] else "No",
                rs['instruction']['op'] if rs['busy'] and rs['instruction'] else "-",
                "Ready" if 'vj' in rs and rs['vj'] is not None else "-",
                "Ready" if 'vk' in rs and rs['vk'] is not None else "-",
                rs['qj'] if 'qj' in rs and rs['qj'] else "-",
                rs['qk'] if 'qk' in rs and rs['qk'] else "-",
                rs['dest'] if 'dest' in rs and rs['dest'] else "-"
            ]
            rs_table.insert("", "end", values=values)


def load_instructions_file():
    file_path = filedialog.askopenfilename(title="Select Instructions File", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
    if file_path:
        with open(file_path, 'r') as file:
            instructionsBox.delete(1.0, END)  # Clear existing content
            instructionsBox.insert(END, file.read())  # Insert file content

# Function to load file content into the Memory Text box
def load_memory_file():
    file_path = filedialog.askopenfilename(title="Select Memory File", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
    if file_path:
        with open(file_path, 'r') as file:
            memoryBox.delete(1.0, END)  # Clear existing content
            memoryBox.insert(END, file.read())  # Insert file content

# Function to update the timeline table
def update_timeline_table(timeline_data):
    # Clear existing data
    for item in timeline_table.get_children():
        timeline_table.delete(item)
    
    # Insert new data
    for instr in timeline_data:
        timeline_table.insert("", "end", values=(
            instr['instruction'],
            instr['issue_cycle'] if instr['issue_cycle'] is not None else "-",
            instr['exec_start'] if instr['exec_start'] is not None else "-",
            instr['exec_end'] if instr['exec_end'] is not None else "-",
            instr['write_cycle'] if instr['write_cycle'] is not None else "-"
        ))

def simulate():
    # Clear the output area
    outputBox.delete(1.0, END)
    
    # Clear the tables
    for item in timeline_table.get_children():
        timeline_table.delete(item)
    for item in rs_table.get_children():
        rs_table.delete(item)
    
    # Get the instructions and memory text
    instructions_text = instructionsBox.get(1.0, END)
    memory_text = memoryBox.get(1.0, END)
    
    # Get the starting PC value
    starting_pc = pc_value.get()
    
    # Get functional unit configuration
    fu_config = {}
    for fu_type, entries in fu_entries.items():
        fu_config[fu_type] = {
            'cycles': entries['cycles'].get(),
            'unit_count': entries['count'].get()
        }
    
    # Define a function to output to the GUI
    def output_to_gui(text):
        outputBox.insert(END, text + "\n")
        outputBox.see(END)  # Scroll to the end
        root.update()  # Update the GUI
    
    # Call the main function from the backend
    timeline_data, state_data = backend.main(instructions_text, memory_text, output_to_gui, starting_pc, fu_config)
    update_timeline_table(timeline_data)
    update_rs_table(state_data['reservation_stations'])
    
    # Update CDB status
    if state_data['cdb']['busy']:
        cdb_status.set(f"Busy - Source: {state_data['cdb']['source_rs']}, Dest: {state_data['cdb']['dest']}")
    else:
        cdb_status.set("Idle")

# File selection buttons for Instructions and Memory
chooseInstructionsButton = Button(root, text="Choose Instructions File", font=("Helvetica", 10), command=load_instructions_file, bg="#666666", fg="white")
chooseInstructionsButton.grid(row=2, column=1, pady=(10, 0), sticky="w", padx=(20, 0))

chooseMemoryButton = Button(root, text="Choose Memory File", font=("Helvetica", 10), command=load_memory_file, bg="#666666", fg="white")
chooseMemoryButton.grid(row=2, column=2, pady=(10, 0), sticky="w", padx=(20, 0))

# Simulation control button
simulateButton = Button(root, text="Run Simulation", font=("Helvetica", 12), command=simulate, bg="#666666", fg="white")
simulateButton.grid(row=3, column=3, pady=(10, 20), sticky="e", padx=(0, 20))

# Main loop
if __name__ == "__main__":
    root.mainloop()
