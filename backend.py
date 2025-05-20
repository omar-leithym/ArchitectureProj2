import ExecutionUnit
from RegisterManager import RegisterManager

# Global Variables
registers = [0] * 8  # Only 8 registers (0-7)
pc_value = 0  # Renamed from program_counter
memory = {}
labels = {}
executable_instructions = []
output_to_gui_global = None

execution_unit = ExecutionUnit.ExecutionUnit()
reg_manager = RegisterManager()

def program_counter():
    global pc_value  # Changed to reference pc_value
    return bool(pc_value)

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

def clear_output_cycles():
    global registers, pc_value, memory, labels, executable_instructions  # Changed program_counter to pc_value
    global output_to_gui_global

    registers = [0] * 8
    pc_value = 0  # Changed program_counter to pc_value
    memory = {}
    labels = {}
    executable_instructions = []
    output_to_gui_global = None

# Utility Functions for reading and parsing instructions
def read_instructions_from_text(instructions_text):
    return instructions_text.splitlines()

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
    global pc_value  # Changed program_counter to pc_value
    if rA is None or rB is None or offset is None:
        output_to_gui_global(f"Error: BEQ instruction missing operands rA={rA}, rB={rB}, offset={offset}")
        return False
    
    if registers[rA] == registers[rB]:
        pc_value = pc_value + 1 + offset  # Changed program_counter to pc_value
        output_to_gui_global(f"BEQ: Branch taken to PC+1+offset = {pc_value}")
        return True
    else:
        output_to_gui_global(f"BEQ: Branch not taken, r{rA}={registers[rA]}, r{rB}={registers[rB]}")
        pc_value += 1  # Changed program_counter to pc_value
        return False

# Call and Return Instructions
def call(label):
    global pc_value  # Changed program_counter to pc_value
    if label is None:
        output_to_gui_global(f"Error: CALL instruction missing label")
        return False
    
    if label in labels:
        registers[1] = pc_value + 1  # Store return address in R1, changed program_counter to pc_value
        pc_value = labels[label]  # Changed program_counter to pc_value
        output_to_gui_global(f"CALL: r1 = {registers[1]}, jumping to label '{label}' at PC = {pc_value}")
        return True
    else:
        output_to_gui_global(f"Error: Label '{label}' not found.")
        return False

def ret():
    global pc_value  # Changed program_counter to pc_value
    pc_value = registers[1]  # Changed program_counter to pc_value
    output_to_gui_global(f"RET: Jumping to address in r1 = {pc_value}")
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
def main(instructions_text, memory_text, output_to_gui, starting_pc, fu_config):
    global pc_value  # Changed program_counter to pc_value
    global labels
    global output_to_gui_global
    global executable_instructions
    global registers, memory

    registers = [0]*8
    memory = {}
    labels = {}
    executable_instructions = []
    
    output_to_gui_global = output_to_gui
    reg_manager.__init__()
    execution_unit.__init__(fu_config)
    
    # Step 1: Get the instruction and memory data as text
    load_memory_from_text(memory_text)
    
    # Step 2: Read instructions
    instruction_lines = read_instructions_from_text(instructions_text)
    base_address = starting_pc
    
    # Step 3: First pass to register labels
    labels = {}
    executable_instructions = []
    for line in instructions_text.splitlines():
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
    pc_value = starting_pc  # Changed program_counter to pc_value

    # Validate starting_pc
    if pc_value < base_address or pc_value >= base_address + instruction_count:  # Changed program_counter to pc_value
        output_to_gui_global(f"Error: Starting PC {pc_value} is out of valid instruction address range.")
        return []

    # Process all instructions at once
    for index in range(len(executable_instructions)):
        line = executable_instructions[index].strip()
        # Parse the instruction
        opcode, rA, rB, rC, imm_or_label, offset = instruction_splitting(line)
        if not opcode:
            continue

        instruction_record = { 
            'op': opcode,
            'dest_reg': f"r{rA}" if rA is not None else None,
            'src_regs': [f"r{rB}", f"r{rC}"] if (rB is not None and rC is not None) else 
                       [f"r{rB}"] if rB is not None else [],
            'offset': imm_or_label if imm_or_label else None
        }
        
        issued_success = execution_unit.issue_instruction(instruction_record, reg_manager)
        if not issued_success:
            output_to_gui_global(f"Issue failed at PC={pc_value + index}: {opcode}")  # Changed program_counter to pc_value
        else:
            execution_unit.execute_process(reg_manager)

    # Run until all instructions complete
    while execution_unit.has_pending_instructions():
        execution_unit.execute_process(reg_manager)

    return execution_unit.get_instruction_timeline()
