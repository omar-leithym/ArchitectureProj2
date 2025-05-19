from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import backend as backend
import ExecutionUnit as ExecutionUnit

# Initialize the main application window
root = Tk()
root.title("Tomasulo Simulator")
root.geometry("1000x800")  # Increased size to accommodate the table
root.configure(bg="#f0f0f0")

# Label for the app title
titleLabel = Label(root, text="Tomasulo Simulator", font=("Helvetica", 16, "bold"), bg="#f0f0f0")
titleLabel.grid(row=0, column=0, columnspan=3, pady=(10, 20), sticky="w", padx=(20, 0))

# Label for syntax instructions
syntaxText = """This is a step-by-step simulator that simulates the instructions using Tomasulo's algorithm without speculation.

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

# PC Frame (same as before)
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

# Configure row weight for output frame
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)
root.grid_rowconfigure(4, weight=2)

# Add this to your frontend file after the stop_simulation function

# Function to execute a single step
def next_step():
    # If this is the first time clicking Next, start the simulation in step mode
    if not hasattr(next_step, "simulation_started"):
        next_step.simulation_started = True
        
        # Clear the output area
        outputBox.delete(1.0, END)
        
        # Get the instructions and memory text
        instructions_text = instructionsBox.get(1.0, END)
        memory_text = memoryBox.get(1.0, END)
        
        # Get the starting PC value
        starting_pc = pc_value.get()
        
        # Define a function to output to the GUI
        def output_to_gui(text):
            outputBox.insert(END, text + "\n")
            outputBox.see(END)  # Scroll to the end
            root.update()  # Update the GUI
        
        # Call the main function from the backend with single_step=True
        backend.main(instructions_text, memory_text, output_to_gui, starting_pc, single_step=True)
    else:
        # Execute the next instruction
        backend.execute_single_step()


# Rest of your functions remain the same...
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

# Function to run the simulation
def simulate():
    # Clear the output area
    outputBox.delete(1.0, END)
    
    # Get the instructions and memory text
    instructions_text = instructionsBox.get(1.0, END)
    memory_text = memoryBox.get(1.0, END)
    
    # Get the starting PC value
    starting_pc = pc_value.get()
    
    # Define a function to output to the GUI
    def output_to_gui(text):
        outputBox.insert(END, text + "\n")
        outputBox.see(END)  # Scroll to the end
        root.update()  # Update the GUI
    
    # Call the main function from the backend
    backend.main(instructions_text, memory_text, output_to_gui, starting_pc)

# Function to stop the simulation
def stop_simulation():
    backend.stop_simulation_func()

def update_timeline_table():
    timeline_data = ExecutionUnit.get_instruction_timeline()
    for instr in timeline_data:
        timeline_table.insert("", "end", values=(
            instr['instruction'],
            instr['issue_cycle'],
            instr['exec_start'],
            instr['exec_end'],
            instr['write_cycle']
        ))

# File selection buttons for Instructions and Memory
chooseInstructionsButton = Button(root, text="Choose Instructions File", font=("Helvetica", 10), command=load_instructions_file, bg="#666666", fg="white")
chooseInstructionsButton.grid(row=2, column=1, pady=(10, 0), sticky="w", padx=(20, 0))

chooseMemoryButton = Button(root, text="Choose Memory File", font=("Helvetica", 10), command=load_memory_file, bg="#666666", fg="white")
chooseMemoryButton.grid(row=2, column=2, pady=(10, 0), sticky="w", padx=(20, 0))

# Simulation control buttons
simulateButton = Button(root, text="Run Simulation", font=("Helvetica", 12), command=simulate, bg="#666666", fg="white")
simulateButton.grid(row=3, column=0, pady=(10, 20), sticky="w", padx=(20, 0))

# Button to stop the simulation
stopButton = Button(root, text="Stop Simulation", font=("Helvetica", 12), command=stop_simulation, bg="#FF6666", fg="white")
stopButton.grid(row=3, column=1, pady=(10, 20), sticky="w", padx=(20, 0))

# Button to execute the next instruction
nextButton = Button(root, text="Next Step", font=("Helvetica", 12), command=next_step, bg="#4CAF50", fg="white")
nextButton.grid(row=3, column=2, pady=(10, 20), sticky="w", padx=(20, 0))

# Main loop
if __name__ == "__main__":
    root.mainloop()