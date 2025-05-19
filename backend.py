# Add these variables to the backend
step_mode = False
step_pending = False

def execute_single_step():
    global step_pending
    step_pending = True

# Global Variables
registers = [0] * 8  # Only 8 registers (0-7)
program_counter = 0
memory = {}
labels = {}
executable_instructions = []
output_to_gui_global = None
stop_simulation = False

# Utility Functions for reading and parsing instructions
def read_instructions_from_text(instructions_text):
    return instructions_text.splitlines()

def load_memory_from_text(memory_text):
    global memory
    memory = {}
    lines = memory_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            parts = line.split()
            if len(parts) >= 2:
                address = int(parts[0], 0)
                value = int(parts[1], 0)
                memory[address] = value
        except ValueError:
            output_to_gui_global(f"Error parsing memory line: {line}")

def load_word(address):
    if address in memory:
        return memory[address]
    return 0

def store_word(address, value):
    memory[address] = value & 0xFFFF  # Ensure 16-bit value

def output_to_gui_globalRegisters(instruction=""):
    output = f"Instruction: {instruction}\n"
    output += "Registers: "
    for i in range(8):
        output += f"r{i}={registers[i]} "
    output += "\n" + f"Memory: {memory}\n"
    output_to_gui_global(output)

def parse_register(reg):
    reg = reg.strip()
    if reg.lower().startswith('r') and reg[1:].isdigit():
        reg_num = int(reg[1:])
        if 0 <= reg_num < 8:  # Only 8 registers (0-7)
            return reg_num
    output_to_gui_global(f"Error: Invalid register {reg}")
    return None

def parse_immediate(value):
    try:
        return int(value, 0)
    except ValueError:
        output_to_gui_global(f"Error: Invalid immediate value '{value}'")
        return None

def instruction_splitting(line):
    line = line.strip()
    if '#' in line:
        line = line.split('#')[0].strip()

    if not line:
        return None, None, None, None, None, None

    parts = line.replace(',', ' ').split()
    opcode = parts[0].upper()

    # Handling Load and Store Instructions with Offset Notation
    if opcode in ['LOAD', 'STORE']:
        if len(parts) != 3:
            output_to_gui_global(f"Error: {opcode} instruction missing operands. line='{line}'")
            return None, None, None, None, None, None
        reg1 = parse_register(parts[1])
        try:
            offset_str, base_register = parts[2].split('(')
            offset = parse_immediate(offset_str)
            reg2 = parse_register(base_register[:-1])
            # Check if offset is within the valid range (-16 to 15)
            if offset < -16 or offset > 15:
                output_to_gui_global(f"Error: Offset {offset} is out of range (-16 to 15)")
                return None, None, None, None, None, None
        except ValueError:
            output_to_gui_global(f"Error: Invalid offset notation. line='{line}'")
            return None, None, None, None, None, None
        
        if opcode == 'STORE':
            return opcode, None, reg2, reg1, offset, None  # rB, offset, rA
        else:  # LOAD
            return opcode, reg1, reg2, None, offset, None  # rA, rB, offset

    # Handling BEQ Instruction
    elif opcode == 'BEQ':
        if len(parts) != 4:
            output_to_gui_global(f"Error: BEQ instruction missing operands. line='{line}'")
            return None, None, None, None, None, None
        rA = parse_register(parts[1])
        rB = parse_register(parts[2])
        offset = parse_immediate(parts[3])
        return opcode, None, rA, rB, offset, None  # rA, rB, offset

    # Handling CALL Instruction
    elif opcode == 'CALL':
        if len(parts) != 2:
            output_to_gui_global(f"Error: CALL instruction missing operands. line='{line}'")
            return None, None, None, None, None, None
        label = parts[1]
        return opcode, None, None, None, label, None  # label

    # Handling RET Instruction
    elif opcode == 'RET':
        return opcode, None, None, None, None, None

    # Handling Arithmetic and Logic Instructions
    elif opcode in ['ADD', 'SUB', 'NOR', 'MUL']:
        if len(parts) != 4:
            output_to_gui_global(f"Error: {opcode} instruction missing operands. line='{line}'")
            return None, None, None, None, None, None
        rA = parse_register(parts[1])
        rB = parse_register(parts[2])
        rC = parse_register(parts[3])
        return opcode, rA, rB, rC, None, None  # rA, rB, rC

    else:
        output_to_gui_global(f"Error: Unrecognized instruction format. line='{line}'")
        return None, None, None, None, None, None

# Load and Store Instructions
def load(rA, offset, rB):
    if rA is None or rB is None or offset is None:
        output_to_gui_global(f"Error: LOAD instruction missing operands rA={rA}, rB={rB}, offset={offset}")
        return
    
    address = (registers[rB] + offset) & 0xFFFF  # 16-bit address
    registers[rA] = load_word(address)
    output_to_gui_global(f"LOAD: r{rA} = Memory[r{rB}({registers[rB]}) + {offset}] = {registers[rA]}")

def store(rA, offset, rB):
    if rA is None or rB is None or offset is None:
        output_to_gui_global(f"Error: STORE instruction missing operands rA={rA}, rB={rB}, offset={offset}")
        return
    
    address = (registers[rB] + offset) & 0xFFFF  # 16-bit address
    store_word(address, registers[rA])
    output_to_gui_global(f"STORE: Memory[r{rB}({registers[rB]}) + {offset}] = r{rA}({registers[rA]})")

# Conditional Branch Instruction
def beq(rA, rB, offset):
    global program_counter
    if rA is None or rB is None or offset is None:
        output_to_gui_global(f"Error: BEQ instruction missing operands rA={rA}, rB={rB}, offset={offset}")
        return False
    
    if registers[rA] == registers[rB]:
        program_counter = program_counter + 1 + offset
        output_to_gui_global(f"BEQ: Branch taken to PC+1+offset = {program_counter}")
        return True
    else:
        output_to_gui_global(f"BEQ: Branch not taken, r{rA}={registers[rA]}, r{rB}={registers[rB]}")
        program_counter += 1
        return False
    #return program_counter

def program_counter():
    return program_counter

# Call and Return Instructions
def call(label):
    global program_counter
    if label is None:
        output_to_gui_global(f"Error: CALL instruction missing label")
        return False
    
    if label in labels:
        registers[1] = program_counter + 1  # Store return address in R1
        program_counter = labels[label]
        output_to_gui_global(f"CALL: r1 = {registers[1]}, jumping to label '{label}' at PC = {program_counter}")
        return True
    else:
        output_to_gui_global(f"Error: Label '{label}' not found.")
        return False

def ret():
    global program_counter
    program_counter = registers[1]
    output_to_gui_global(f"RET: Jumping to address in r1 = {program_counter}")
    return True

# Arithmetic and Logic Instructions
def add(rA, rB, rC):
    if rA is None or rB is None or rC is None:
        output_to_gui_global(f"Error: ADD instruction missing operands rA={rA}, rB={rB}, rC={rC}")
        return
    
    registers[rA] = (registers[rB] + registers[rC]) & 0xFFFF  # 16-bit result
    output_to_gui_global(f"ADD: r{rA} = r{rB}({registers[rB]}) + r{rC}({registers[rC]}) = {registers[rA]}")

def sub(rA, rB, rC):
    if rA is None or rB is None or rC is None:
        output_to_gui_global(f"Error: SUB instruction missing operands rA={rA}, rB={rB}, rC={rC}")
        return
    
    registers[rA] = (registers[rB] - registers[rC]) & 0xFFFF  # 16-bit result
    output_to_gui_global(f"SUB: r{rA} = r{rB}({registers[rB]}) - r{rC}({registers[rC]}) = {registers[rA]}")

def nor(rA, rB, rC):
    if rA is None or rB is None or rC is None:
        output_to_gui_global(f"Error: NOR instruction missing operands rA={rA}, rB={rB}, rC={rC}")
        return
    
    registers[rA] = ~(registers[rB] | registers[rC]) & 0xFFFF  # 16-bit result
    output_to_gui_global(f"NOR: r{rA} = ~(r{rB}({registers[rB]}) | r{rC}({registers[rC]})) = {registers[rA]}")

def mul(rA, rB, rC):
    if rA is None or rB is None or rC is None:
        output_to_gui_global(f"Error: MUL instruction missing operands rA={rA}, rB={rB}, rC={rC}")
        return
    
    registers[rA] = (registers[rB] * registers[rC]) & 0xFFFF  # 16-bit result
    output_to_gui_global(f"MUL: r{rA} = r{rB}({registers[rB]}) * r{rC}({registers[rC]}) = {registers[rA]}")

# Dictionary of instructions
instructions = {
    'LOAD': load, 'STORE': store,
    'BEQ': beq,
    'CALL': call, 'RET': ret,
    'ADD': add, 'SUB': sub, 'NOR': nor, 'MUL': mul
}

# Main Function
def main(instructions_text, memory_text, output_to_gui, starting_pc, single_step=False):
    global program_counter
    global labels
    global output_to_gui_global
    global executable_instructions
    global stop_simulation
    global step_mode
    global step_pending
    
    output_to_gui_global = output_to_gui
    step_mode = single_step
    step_pending = not single_step  # If not in single step mode, allow first instruction to execute
    
    # Reset global variables
    global registers, memory, labels
    registers = [0] * 8  # Only 8 registers (0-7)
    memory = {}
    labels = {}
    stop_simulation = False
    
    # Step 1: Get the instruction and memory data as text
    load_memory_from_text(memory_text)
    
    # Step 2: Read instructions
    instruction_lines = read_instructions_from_text(instructions_text)
    base_address = starting_pc
    
    # Step 3: First pass to register labels
    labels = {}
    executable_instructions = []
    for line_number, line in enumerate(instruction_lines):
        stripped_line = line.strip()

        # Remove comments
        if '#' in stripped_line:
            stripped_line = stripped_line.split('#')[0].strip()

        # Skip empty lines
        if not stripped_line:
            continue

        # Check for labels
        if stripped_line.endswith(':'):
            label_name = stripped_line[:-1].strip()
            # Map label to the instruction address
            labels[label_name] = base_address + len(executable_instructions)
        else:
            # Append the executable instruction
            executable_instructions.append(stripped_line)

    # Step 4: Execute instructions
    instruction_count = len(executable_instructions)
    program_counter = starting_pc  # Initialize PC to user-specified starting address
    running = True  # Flag to control the execution loop

    # Validate starting_pc
    if program_counter < base_address or program_counter >= base_address + instruction_count:
        output_to_gui_global(f"Error: Starting PC {program_counter} is out of valid instruction address range.")
        return

    while not stop_simulation and running and 0 <= (program_counter - base_address) < instruction_count:
        # If in step mode, wait for step_pending to be true
        if step_mode and not step_pending:
            break
        
        step_pending = False  # Reset step pending flag
        
        # Calculate the index in the executable_instructions list
        index = program_counter - base_address

        # Fetch the current instruction
        try:
            line = executable_instructions[index].strip()
        except IndexError:
            output_to_gui_global(f"Error: Program counter {program_counter} out of bounds.")
            break

        original_line = line  # Preserve the original line for debugging

        # Parse the instruction
        opcode, rA, rB, rC, imm_or_label, offset = instruction_splitting(line)
        if not opcode:
            # If parsing failed, skip to the next instruction
            program_counter += 1
            continue

        # Execute the instruction based on its opcode
        if opcode in instructions:
            # Load and Store Instructions
            if opcode == 'LOAD':
                instructions[opcode](rA, imm_or_label, rB)
                program_counter += 1
            elif opcode == 'STORE':
                instructions[opcode](rC, imm_or_label, rB)
                program_counter += 1
            # Conditional Branch Instruction
            elif opcode == 'BEQ':
                branch_taken = instructions[opcode](rB, rC, imm_or_label)
                # program_counter is updated inside the beq function
            # Call and Return Instructions
            elif opcode == 'CALL':
                call_taken = instructions[opcode](imm_or_label)
                if not call_taken:
                    program_counter += 1
            elif opcode == 'RET':
                ret_taken = instructions[opcode]()
                if not ret_taken:
                    program_counter += 1
            # Arithmetic and Logic Instructions
            elif opcode in ['ADD', 'SUB', 'NOR', 'MUL']:
                instructions[opcode](rA, rB, rC)
                program_counter += 1
            else:
                output_to_gui_global(f"Error: Unhandled opcode '{opcode}'")
                program_counter += 1
        else:
            output_to_gui_global(f"Error: Unknown opcode '{opcode}'")
            program_counter += 1

        # Output the register states after execution
        output_to_gui_globalRegisters(instruction=original_line)

        # Ensure r0 remains zero
        registers[0] = 0