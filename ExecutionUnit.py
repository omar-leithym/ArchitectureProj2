import backend
from RegisterManager import RegisterManager 

class ExecutionUnit:
    def __init__(self, fu_config=None):
        # Default configuration if none provided
        default_config = {
            'LOAD': {'cycles': 6, 'unit_count': 2},
            'STORE': {'cycles': 6, 'unit_count': 4},  # Increased store units to 4
            'ADD_SUB': {'cycles': 2, 'unit_count': 4},
            'MUL': {'cycles': 10, 'unit_count': 2},
            'NOR': {'cycles': 1, 'unit_count': 2},
            'BEQ': {'cycles': 1, 'unit_count': 2},
            'CALL_RET': {'cycles': 1, 'unit_count': 1}
        }
        
        # Use provided config or default
        config = fu_config if fu_config else default_config
        
        # Create reservation stations for each functional unit type
        self.reservation_stations = {}
        for fu_type, settings in config.items():
            self.reservation_stations[fu_type] = [
                {
                    'busy': False,
                    'instruction': None,
                    'vj': None,  # Value of first operand
                    'vk': None,  # Value of second operand
                    'qj': None,  # Reservation station producing first operand
                    'qk': None,  # Reservation station producing second operand
                    'dest': None,  # Destination register
                    'executing': False,
                    'cycles_left': 0,
                    'flushed': False  # New field to track if instruction was flushed
                } for _ in range(settings['unit_count'])
            ]
            
        # Store cycle information for each FU type
        self.fu_cycles = {fu_type: settings['cycles'] for fu_type, settings in config.items()}
        
        # Common Data Bus for result broadcasting
        self.cdb = {
            'busy': False,
            'result': None,
            'dest': None,
            'source_rs': None
        }

        # Track instructions in each stage
        self.waiting_to_execute_instructions = []
        self.executing_instructions = []
        self.completed_instructions = []
        self.instruction_history = []
        self.flushed_instructions = []  # Track flushed instructions

        # Branch prediction and flush state
        self.prediction_state = "not_taken"
        self.branch_in_progress = False
        self.instructions_to_flush = []
        self.branch_target_pc = None
        self.last_branch_pc = None

        # Cycle counter
        self.current_cycle = 0

    def issue_instruction(self, instruction, reg_manager):
        op = instruction['op'].upper()
        fu_type = self._get_functional_unit_type(op)

        # Check if there's an available reservation station for this type
        rs_available = False
        rs_index = -1
        
        for i, rs in enumerate(self.reservation_stations[fu_type]):
            if not rs['busy']:
                rs_available = True
                rs_index = i
                break
                
        if not rs_available:
            return False  # All reservation stations are busy
                
        # Get reservation station
        rs = self.reservation_stations[fu_type][rs_index]
        
        # Mark the reservation station as busy
        rs['busy'] = True
        rs['instruction'] = instruction
        rs['dest'] = instruction.get('dest_reg')
        rs['flushed'] = False  # Initialize as not flushed
        
        # Get source registers
        src_regs = instruction.get('src_regs', [])
        
        # Check if operands are available or need to wait
        if len(src_regs) >= 1:
            if reg_manager.is_ready(src_regs[0]):
                rs['vj'] = True  # Just mark as available
                rs['qj'] = None
            else:
                rs['vj'] = None
                rs['qj'] = reg_manager.get_status(src_regs[0])
        
        if len(src_regs) >= 2:
            if reg_manager.is_ready(src_regs[1]):
                rs['vk'] = True  # Just mark as available
                rs['qk'] = None
            else:
                rs['vk'] = None
                rs['qk'] = reg_manager.get_status(src_regs[1])
        
        # Mark destination register as busy with this reservation station
        if rs['dest'] and op not in ('STORE', 'BEQ', 'RET'):
            try:
                reg_manager.set_busy(rs['dest'], f"{fu_type}_{rs_index}")
            except ValueError:
                pass  # Handle R0 case
        
        # Instruction record for tracking
        instr_record = {
            'instruction': instruction,
            'fu_type': fu_type,
            'rs_index': rs_index,
            'issue_cycle': self.current_cycle,
            'exec_start': None,
            'exec_end': None,
            'write_cycle': None,
            'flushed': False,  # Track if instruction was flushed
            'pc': instruction.get('pc')  # Store PC for branch handling
        }
        self.waiting_to_execute_instructions.append(instr_record)
        self.instruction_history.append(instr_record)
        
        # Track branch instructions
        if fu_type in ('BEQ', 'CALL_RET'):
            self.prediction_state = "not_taken"  # Default prediction
            self.branch_in_progress = True
            self.last_branch_pc = instruction.get('pc')
            # Track instructions issued after this branch for potential flushing
            self.instructions_to_flush = []
        elif self.branch_in_progress:
            # If we're issuing after a branch, track for potential flush
            self.instructions_to_flush.append(instruction)
            
        return True
        
    def execute_process(self, reg_manager):
        self.current_cycle += 1
        
        # First, handle CDB from previous cycle
        if self.cdb['busy']:
            # Broadcast result to all reservation stations
            for fu_type in self.reservation_stations:
                for rs in self.reservation_stations[fu_type]:
                    if rs['busy'] and not rs['flushed']:
                        # Update operands if they were waiting for this result
                        if rs['qj'] == self.cdb['source_rs']:
                            rs['vj'] = True
                            rs['qj'] = None
                        if rs['qk'] == self.cdb['source_rs']:
                            rs['vk'] = True
                            rs['qk'] = None
            
            # Update register file
            if self.cdb['dest']:
                reg_manager.set_ready(self.cdb['dest'])
            
            # Clear CDB
            self.cdb['busy'] = False
            self.cdb['result'] = None
            self.cdb['dest'] = None
            self.cdb['source_rs'] = None

        # Check for completed branches - IMPROVED BRANCH HANDLING
        completed_branch = False
        for instr_record in list(self.executing_instructions):
            fu_type = instr_record['fu_type']
            rs_index = instr_record['rs_index']
            rs = self.reservation_stations[fu_type][rs_index]
            
            if (fu_type in ('BEQ', 'CALL_RET') and 
                rs['executing'] and 
                rs['cycles_left'] <= 0 and 
                self.branch_in_progress):
                
                # For BEQ, check actual branch outcome
                if fu_type == 'BEQ' and instr_record['instruction']['op'].upper() == 'BEQ':
                    # Get the actual PC value from backend
                    actual_pc = backend.program_counter()
                    branch_pc = instr_record['pc']
                    
                    # Determine if branch was taken based on PC value
                    branch_taken = (actual_pc != branch_pc + 2)
                    
                    # If prediction was wrong (we predicted not taken), flush instructions
                    if branch_taken and self.prediction_state == "not_taken":
                        self._flush_incorrect_instructions(branch_pc)
                
                # Mark branch as no longer in progress
                self.branch_in_progress = False
                completed_branch = True
                break  # Only process one branch completion at a time

        # Start execution for ready reservation stations
        newly_started = []
        for instr_record in list(self.waiting_to_execute_instructions):
            fu_type = instr_record['fu_type']
            rs_index = instr_record['rs_index']
            rs = self.reservation_stations[fu_type][rs_index]
            
            if rs['busy'] and not rs['executing'] and not rs['flushed']:
                # Check if all operands are ready
                operands_ready = True
                op = instr_record['instruction']['op'].upper()
                
                # For operations that need operands
                if op not in ('CALL', 'RET'):
                    if op == 'STORE':
                        # STORE needs both registers (base and value)
                        if rs['qj'] is not None or rs['qk'] is not None:
                            operands_ready = False
                    elif op == 'LOAD':
                        # LOAD might need a base register
                        if rs['qj'] is not None:
                            operands_ready = False
                    else:
                        # Other operations need both operands if applicable
                        if rs['qj'] is not None or rs['qk'] is not None:
                            operands_ready = False
                
                # Only start execution if operands are ready AND
                # either no branch is in progress OR this is a branch instruction
                if operands_ready and (not self.branch_in_progress or fu_type in ('BEQ', 'CALL_RET')):
                    rs['executing'] = True
                    rs['cycles_left'] = self.fu_cycles[fu_type]
                    
                    # Update instruction record
                    instr_record['exec_start'] = self.current_cycle
                    instr_record['exec_end'] = self.current_cycle + rs['cycles_left'] - 1
                    self.executing_instructions.append(instr_record)
                    newly_started.append(instr_record)
                    
                    # If this is a branch/call/ret, track it as potentially causing hazards
                    if fu_type in ('BEQ', 'CALL_RET'):
                        # Track instructions to potentially flush if prediction is wrong
                        self.instructions_to_flush = [
                            rec['instruction'] for rec in self.waiting_to_execute_instructions
                            if rec not in newly_started
                        ]
                    
                    # Execute the actual instruction
                    self._execute_instruction(rs['instruction'])
        
        # Remove newly started instructions from waiting list
        for rec in newly_started:
            self.waiting_to_execute_instructions.remove(rec)
        
        # Update cycles left for executing instructions
        for fu_type in self.reservation_stations:
            for rs_index, rs in enumerate(self.reservation_stations[fu_type]):
                if rs['busy'] and rs['executing'] and rs['cycles_left'] > 0 and not rs['flushed']:
                    rs['cycles_left'] -= 1
        
        # Check for completed executions (only if not a branch that just completed)
        if not completed_branch:
            finished = []
            for instr_record in list(self.executing_instructions):
                fu_type = instr_record['fu_type']
                rs_index = instr_record['rs_index']
                rs = self.reservation_stations[fu_type][rs_index]
                
                if rs['busy'] and rs['executing'] and rs['cycles_left'] <= 0 and not self.cdb['busy'] and not rs['flushed']:
                    # Instruction has completed execution, put result on CDB
                    self.cdb['busy'] = True
                    self.cdb['result'] = True  # Just mark as available
                    self.cdb['dest'] = rs['dest']
                    self.cdb['source_rs'] = f"{fu_type}_{rs_index}"
                    
                    # Update instruction record
                    instr_record['write_cycle'] = self.current_cycle + 1
                    self.completed_instructions.append(instr_record)
                    finished.append(instr_record)
                    
                    # Free up reservation station
                    rs['busy'] = False
                    rs['instruction'] = None
                    rs['vj'] = None
                    rs['vk'] = None
                    rs['qj'] = None
                    rs['qk'] = None
                    rs['dest'] = None
                    rs['executing'] = False
                    rs['cycles_left'] = 0
                    rs['flushed'] = False
                    
                    # Only process one completion per cycle (CDB limitation)
                    break
            
            # Remove finished instructions from executing list
            for rec in finished:
                self.executing_instructions.remove(rec)

    def _execute_instruction(self, instruction):
        """Actually execute the instruction to see results"""
        op = instruction['op'].upper()
        
        if op == 'LOAD':
            dest_reg = instruction.get('dest_reg')
            src_reg = instruction.get('src_regs', [''])[0] if instruction.get('src_regs') else None
            offset = instruction.get('offset')
            
            if dest_reg and src_reg and offset is not None:
                dest_num = int(dest_reg[1:]) if dest_reg[0].lower() == 'r' else None
                src_num = int(src_reg[1:]) if src_reg[0].lower() == 'r' else None
                
                if dest_num is not None and src_num is not None:
                    backend.load(dest_num, offset, src_num)
                    
        # In ExecutionUnit.py, in _execute_instruction:
        elif op == 'STORE':
            value_reg = instruction.get('value_reg')
            base_reg = instruction.get('base_reg')
            offset = instruction.get('offset')
            
            if value_reg and base_reg and offset is not None:
                value_num = int(value_reg[1:]) if value_reg[0].lower() == 'r' else None
                base_num = int(base_reg[1:]) if base_reg[0].lower() == 'r' else None
                
                if value_num is not None and base_num is not None:
                    backend.store(value_num, offset, base_num)

                            
        elif op == 'ADD':
            dest_reg = instruction.get('dest_reg')
            src_regs = instruction.get('src_regs', [])
            
            if dest_reg and len(src_regs) >= 2:
                dest_num = int(dest_reg[1:]) if dest_reg[0].lower() == 'r' else None
                src1_num = int(src_regs[0][1:]) if src_regs[0][0].lower() == 'r' else None
                src2_num = int(src_regs[1][1:]) if src_regs[1][0].lower() == 'r' else None
                
                if dest_num is not None and src1_num is not None and src2_num is not None:
                    backend.add(dest_num, src1_num, src2_num)
                    
        elif op == 'SUB':
            dest_reg = instruction.get('dest_reg')
            src_regs = instruction.get('src_regs', [])
            
            if dest_reg and len(src_regs) >= 2:
                dest_num = int(dest_reg[1:]) if dest_reg[0].lower() == 'r' else None
                src1_num = int(src_regs[0][1:]) if src_regs[0][0].lower() == 'r' else None
                src2_num = int(src_regs[1][1:]) if src_regs[1][0].lower() == 'r' else None
                
                if dest_num is not None and src1_num is not None and src2_num is not None:
                    backend.sub(dest_num, src1_num, src2_num)
                    
        elif op == 'MUL':
            dest_reg = instruction.get('dest_reg')
            src_regs = instruction.get('src_regs', [])
            
            if dest_reg and len(src_regs) >= 2:
                dest_num = int(dest_reg[1:]) if dest_reg[0].lower() == 'r' else None
                src1_num = int(src_regs[0][1:]) if src_regs[0][0].lower() == 'r' else None
                src2_num = int(src_regs[1][1:]) if src_regs[1][0].lower() == 'r' else None
                
                if dest_num is not None and src1_num is not None and src2_num is not None:
                    backend.mul(dest_num, src1_num, src2_num)
                    
        elif op == 'NOR':
            dest_reg = instruction.get('dest_reg')
            src_regs = instruction.get('src_regs', [])
            
            if dest_reg and len(src_regs) >= 2:
                dest_num = int(dest_reg[1:]) if dest_reg[0].lower() == 'r' else None
                src1_num = int(src_regs[0][1:]) if src_regs[0][0].lower() == 'r' else None
                src2_num = int(src_regs[1][1:]) if src_regs[1][0].lower() == 'r' else None
                
                if dest_num is not None and src1_num is not None and src2_num is not None:
                    backend.nor(dest_num, src1_num, src2_num)
                    
        elif op == 'BEQ':
            src_regs = instruction.get('src_regs', [])
            offset = instruction.get('offset')
            
            if len(src_regs) >= 2 and offset is not None:
                src1_num = int(src_regs[0][1:]) if src_regs[0][0].lower() == 'r' else None
                src2_num = int(src_regs[1][1:]) if src_regs[1][0].lower() == 'r' else None
                
                if src1_num is not None and src2_num is not None:
                    # Call backend's beq but don't modify PC here - that's done in backend
                    taken = backend.beq(src1_num, src2_num, offset)
                    # Update branch prediction state based on actual outcome
                    self.prediction_state = "taken" if taken else "not_taken"
                    
        elif op == 'CALL':
            label = instruction.get('offset')
            if label:
                backend.call(label)
                
        elif op == 'RET':
            backend.ret()

# In ExecutionUnit.py:

    def _flush_incorrect_instructions(self, branch_pc):
        """Remove all instructions issued after the branch"""
        # Find all instructions with PC > branch_pc
        to_flush = []
        
        # First, identify all registers that need to be restored
        registers_to_restore = {}
        
        # Check waiting instructions
        for instr_record in list(self.waiting_to_execute_instructions):
            if instr_record['pc'] > branch_pc:
                to_flush.append(instr_record)
                instr_record['flushed'] = True
                
                # Mark the RS as flushed and free it
                rs = self.reservation_stations[instr_record['fu_type']][instr_record['rs_index']]
                rs['flushed'] = True
                rs['busy'] = False
                
                # If it has a destination register, track it for restoration
                if rs['dest']:
                    registers_to_restore[rs['dest']] = True
        
        # Check executing instructions
        for instr_record in list(self.executing_instructions):
            if instr_record['pc'] > branch_pc:
                to_flush.append(instr_record)
                instr_record['flushed'] = True
                
                # Mark the RS as flushed and free it
                rs = self.reservation_stations[instr_record['fu_type']][instr_record['rs_index']]
                rs['flushed'] = True
                rs['busy'] = False
                rs['executing'] = False
                
                # If it has a destination register, track it for restoration
                if rs['dest']:
                    registers_to_restore[rs['dest']] = True
        
        # Remove flushed instructions from waiting list
        self.waiting_to_execute_instructions = [
            i for i in self.waiting_to_execute_instructions if not i['flushed']
        ]
        
        # Remove flushed instructions from executing list
        self.executing_instructions = [
            i for i in self.executing_instructions if not i['flushed']
        ]
        
        # Add to flushed instructions list
        self.flushed_instructions.extend(to_flush)
        
        # Mark flushed in instruction history
        for rec in self.instruction_history:
            if rec['pc'] > branch_pc:
                rec['flushed'] = True
        
        return registers_to_restore



    def _get_functional_unit_type(self, op):
        if op in ('LOAD', 'STORE'):
            return op
        elif op in ('ADD', 'SUB'):
            return 'ADD_SUB'
        elif op in ('BEQ', 'CALL', 'RET'):
            return 'BEQ' if op == 'BEQ' else 'CALL_RET'
        else:
            return op  # MUL, NOR

    def get_state(self):
        """
        Return a snapshot of the current cycle, plus what's waiting, executing, and completed.
        Useful if you want to print cycle‐by‐cycle FU usage.
        """
        return {
            'cycle': self.current_cycle,
            'issued': [i['instruction'] for i in self.waiting_to_execute_instructions if not i['flushed']],
            'executing': [
                (i['instruction'], f"Cycle {self.current_cycle - i['exec_start'] + 1}/"
                                f"{i['exec_end'] - i['exec_start'] + 1}")
                for i in self.executing_instructions if not i['flushed']
            ],
            'completed': [i['instruction'] for i in self.completed_instructions if not i['flushed']],
            'reservation_stations': self.reservation_stations,
            'cdb': self.cdb
        }

    def has_pending_instructions(self):
        """Check if there are any instructions still in progress"""
        # Only count non-flushed instructions
        waiting_count = sum(1 for i in self.waiting_to_execute_instructions if not i['flushed'])
        executing_count = sum(1 for i in self.executing_instructions if not i['flushed'])
        return waiting_count > 0 or executing_count > 0
        
    def get_instruction_timeline(self):
        timeline = []
        for rec in self.instruction_history:
            op = rec['instruction']['op'].upper()
            src_regs = rec['instruction'].get('src_regs', [])
            dest_reg = rec['instruction'].get('dest_reg', '')
            offset = rec['instruction'].get('offset', '')

            if op == 'LOAD':
                if len(src_regs) >= 1:
                    inst_str = f"{op} {dest_reg}, {offset}({src_regs[0]})"
                else:
                    inst_str = f"{op} {dest_reg}, {offset}"
            elif op == 'STORE':
                value_reg = rec['instruction'].get('value_reg', '')
                base_reg = rec['instruction'].get('base_reg', '')
                if value_reg and base_reg:
                    inst_str = f"{op} {value_reg}, {offset}({base_reg})"
                elif len(src_regs) >= 2:
                    inst_str = f"{op} {src_regs[0]}, {offset}({src_regs[1]})"
                else:
                    inst_str = f"{op} {offset}"
            elif op == 'BEQ':
                if len(src_regs) >= 2:
                    inst_str = f"{op} {src_regs[0]}, {src_regs[1]}, {offset}"
                else:
                    inst_str = f"{op} {offset}"
            elif op in ('CALL', 'RET'):
                if op == 'CALL' and offset:
                    inst_str = f"{op} {offset}"
                else:
                    inst_str = op
            else:
                if len(src_regs) >= 2:
                    inst_str = f"{op} {dest_reg}, {src_regs[0]}, {src_regs[1]}"
                else:
                    inst_str = op

            timeline.append({
                        'instruction': inst_str,
                        'issue_cycle': rec['issue_cycle'],
                        'exec_start': rec['exec_start'],
                        'exec_end': rec['exec_end'],
                        'write_cycle': rec['write_cycle'],
                        'flushed': rec.get('flushed', False)  # Include flushed status
                    })
        return timeline

