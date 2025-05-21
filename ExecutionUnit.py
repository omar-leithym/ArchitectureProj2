import backend
from RegisterManager import RegisterManager 

class ExecutionUnit:
    def __init__(self, fu_config=None):
        default_config = {
            'LOAD': {'cycles': 6, 'unit_count': 2},
            'STORE': {'cycles': 6, 'unit_count': 2},
            'ADD_SUB': {'cycles': 2, 'unit_count': 4},
            'MUL': {'cycles': 10, 'unit_count': 2},
            'NOR': {'cycles': 1, 'unit_count': 2},
            'BEQ': {'cycles': 1, 'unit_count': 2},
            'CALL_RET': {'cycles': 1, 'unit_count': 1}
        }
        

        config = fu_config if fu_config else default_config
        
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
                    'cycles_left': 0
                } for _ in range(settings['unit_count'])
            ]
            
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

        # Branch prediction and flush state
        self.prediction_state = "not_taken"
        self.branch_in_progress = False
        self.instructions_to_flush = []

            # Statistics for IPC and branch prediction
        self.completed_instruction_count = 0
        self.total_cycles = 0
        self.mispredictions = 0
        self.total_branches = 0
        # Cycle counter
        self.current_cycle = 0

    def issue_instruction(self, instruction, reg_manager):
        op = instruction['op'].upper()
        fu_type = self._get_functional_unit_type(op)

        # If branch is being processed, stall new instructions
        if self.branch_in_progress and fu_type not in ('BEQ', 'CALL_RET'):
            return False
            
        rs_available = False
        rs_index = -1
        
        for i, rs in enumerate(self.reservation_stations[fu_type]):
            if not rs['busy']:
                rs_available = True
                rs_index = i
                break
                
        if not rs_available:
            return False 
        
        # Get reservation station
        rs = self.reservation_stations[fu_type][rs_index]
        
        # Mark the reservation station as busy
        rs['busy'] = True
        rs['instruction'] = instruction
        rs['dest'] = instruction.get('dest_reg')
        
        # Get source registers
        src_regs = instruction.get('src_regs', [])
        
        # Check if operands are available or need to wait
        if len(src_regs) >= 1:
            if reg_manager.is_ready(src_regs[0]):
                rs['vj'] = True  # Just mark as available
                rs['qj'] = None
            else:
                rs['vj'] = None
                rs['qj'] = reg_manager.get_status(src_regs[0])  # Use get_status instead of get_producer
        
        if len(src_regs) >= 2:
            if reg_manager.is_ready(src_regs[1]):
                rs['vk'] = True  # Just mark as available
                rs['qk'] = None
            else:
                rs['vk'] = None
                rs['qk'] = reg_manager.get_status(src_regs[1])  # Use get_status instead of get_producer
        
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
            'write_cycle': None
        }
        self.waiting_to_execute_instructions.append(instr_record)
        self.instruction_history.append(instr_record)
        if fu_type == 'BEQ':
            offset = instruction.get('offset')
            # Make sure offset is a valid integer
            if offset is None:
                offset = 0
            else:
                try:
                    offset = int(offset)
                except (ValueError, TypeError):
                    offset = 0
                    
            # Predict taken if offset is negative (backward branch, likely a loop)
            self.prediction_state = "taken" if offset < 0 else "not_taken"
            self.branch_in_progress = True
            self.instructions_to_flush = []
            # Add all instructions after this one to the flush list
            for instr in self.waiting_to_execute_instructions:
                if instr['issue_cycle'] > self.current_cycle:
                    self.instructions_to_flush.append(instr['instruction'])
        
        return True

        
    def execute_process(self, reg_manager):
        self.current_cycle += 1
        self.total_cycles +=1
        
        # First, handle CDB from previous cycle
        if self.cdb['busy']:
            # Broadcast result to all reservation stations
            for fu_type in self.reservation_stations:
                for rs in self.reservation_stations[fu_type]:
                    if rs['busy']:
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

        
        # Check for completed branches
        for instr_record in list(self.executing_instructions):
            fu_type = instr_record['fu_type']
            rs_index = instr_record['rs_index']
            rs = self.reservation_stations[fu_type][rs_index]
            
            if fu_type == 'BEQ' and self.current_cycle >= instr_record['exec_end']:
                # Get actual branch outcome
                src_regs = instr_record['instruction'].get('src_regs', [])
                offset = instr_record['instruction'].get('offset', 0)
                
                # Determine if branch was actually taken
                actual_taken = False
                if len(src_regs) >= 2:
                    reg1 = int(src_regs[0][1:])  # Remove 'r' prefix
                    reg2 = int(src_regs[1][1:])
                    actual_taken = (backend.registers[reg1] == backend.registers[reg2])
                
                # Check if prediction was correct
                predicted_taken = (self.prediction_state == "taken")
                
                # Update branch statistics
                self.total_branches += 1
                
                if actual_taken != predicted_taken:
                    # Misprediction occurred
                    self.mispredictions += 1
                    self._flush_incorrect_instructions()
                
                self.branch_in_progress = False
            
            # Handle CALL_RET separately (this was missing in your code)
            elif fu_type == 'CALL_RET' and self.current_cycle >= instr_record['exec_end']:
                # No prediction needed for CALL/RET, just clear the branch in progress flag
                self.branch_in_progress = False


        # Start execution for ready reservation stations
        newly_started = []
        for instr_record in list(self.waiting_to_execute_instructions):
            fu_type = instr_record['fu_type']
            rs_index = instr_record['rs_index']
            rs = self.reservation_stations[fu_type][rs_index]
            
            if rs['busy'] and not rs['executing']:
                # Check if all operands are ready - this was the issue!
                # For most instructions, we need both operands
                # But for some instructions like LOAD, STORE, CALL, RET, we don't need both
                operands_ready = True
                op = instr_record['instruction']['op'].upper()
                
                # For operations that need operands
                if op not in ('CALL', 'RET'):
                    if op == 'STORE':
                        # STORE needs the source register
                        operands_ready = rs['qj'] is None
                    elif op == 'LOAD':
                        # LOAD might need a base register
                        if rs['qj'] is not None:
                            operands_ready = False
                    else:
                        # Other operations need both operands if applicable
                        if rs['qj'] is not None or rs['qk'] is not None:
                            operands_ready = False
                
                # Start execution if operands are ready and not blocked by branch
                if operands_ready and (not self.branch_in_progress or fu_type in ('BEQ', 'CALL_RET')):
                    rs['executing'] = True
                    rs['cycles_left'] = self.fu_cycles[fu_type]
                    
                    # Update instruction record
                    instr_record['exec_start'] = self.current_cycle
                    instr_record['exec_end'] = self.current_cycle + rs['cycles_left'] - 1
                    self.executing_instructions.append(instr_record)
                    newly_started.append(instr_record)
                    
                    # Execute the actual instruction
                    self._execute_instruction(rs['instruction'])
        
        # Remove newly started instructions from waiting list
        for rec in newly_started:
            self.waiting_to_execute_instructions.remove(rec)
        
        # Update cycles left for executing instructions
        for fu_type in self.reservation_stations:
            for rs_index, rs in enumerate(self.reservation_stations[fu_type]):
                if rs['busy'] and rs['executing'] and rs['cycles_left'] > 0:
                    rs['cycles_left'] -= 1
        
        # Check for completed executions
        finished = []
        for instr_record in list(self.executing_instructions):
            fu_type = instr_record['fu_type']
            rs_index = instr_record['rs_index']
            rs = self.reservation_stations[fu_type][rs_index]
            
            if rs['busy'] and rs['executing'] and rs['cycles_left'] <= 0:
             if not self.cdb['busy']:
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

                self.completed_instruction_count += 1
                
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
                    
        elif op == 'STORE':
            src_reg = instruction.get('src_regs', [''])[0] if instruction.get('src_regs') else None
            dest_reg = instruction.get('dest_reg')
            offset = instruction.get('offset')
            
            if src_reg and offset is not None:
                src_num = int(src_reg[1:]) if src_reg[0].lower() == 'r' else None
                dest_num = int(dest_reg[1:]) if dest_reg and dest_reg[0].lower() == 'r' else None
                
                if src_num is not None and dest_num is not None:
                    backend.store(dest_num, offset, src_num)
                    
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
                    backend.beq(src1_num, src2_num, offset)
                    
        elif op == 'CALL':
            label = instruction.get('offset')
            if label:
                backend.call(label)
                
        elif op == 'RET':
            backend.ret()

    def _flush_incorrect_instructions(self):
        """Remove all instructions issued after the branch"""
        # Clear reservation stations
        to_flush = set(self.instructions_to_flush)

        for fu_type in self.reservation_stations:
            for rs in self.reservation_stations[fu_type]:
                if rs['busy'] and rs['instruction'] in to_flush:
                    rs['busy'] = False
                    rs['instruction'] = None
                    rs['vj'] = None
                    rs['vk'] = None
                    rs['qj'] = None
                    rs['qk'] = None
                    rs['dest'] = None
                    rs['executing'] = False
                    rs['cycles_left'] = 0
        
        # Remove from instruction_history (so timeline doesn't show flushed instrs)
        self.instruction_history = [
            i for i in self.instruction_history if i['instruction'] not in to_flush
        ]
        
        # Remove from waiting and executing lists
        self.waiting_to_execute_instructions = [
            i for i in self.waiting_to_execute_instructions if i['instruction'] not in to_flush
        ]
        self.executing_instructions = [
            i for i in self.executing_instructions if i['instruction'] not in to_flush
        ]
        
        # Clear the flush set for next branch
        self.instructions_to_flush = []

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
            'issued': [i['instruction'] for i in self.waiting_to_execute_instructions],
            'executing': [
                (i['instruction'], f"Cycle {self.current_cycle - i['exec_start'] + 1}/"
                                f"{i['exec_end'] - i['exec_start']}")
                for i in self.executing_instructions
            ],
            'completed': [i['instruction'] for i in self.completed_instructions],
            'reservation_stations': self.reservation_stations,
            'cdb': self.cdb,
            'statistics': self.get_statistics()
        }


    def has_pending_instructions(self):
        """Check if there are any instructions still in progress"""
        return len(self.waiting_to_execute_instructions) > 0 or len(self.executing_instructions) > 0
        
    def get_instruction_timeline(self):
        timeline = []
        for rec in self.instruction_history:
            op       = rec['instruction']['op'].upper()
            src_regs = rec['instruction'].get('src_regs', [])
            dest_reg = rec['instruction'].get('dest_reg', '')
            offset   = rec['instruction'].get('offset', '')

            if op in ('LOAD', 'STORE'):
                if len(src_regs) >= 1:
                    inst_str = f"{op} {dest_reg}, {offset}({src_regs[0]})"
                else:
                    inst_str = f"{op} {dest_reg}, {offset}"
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
                'write_cycle': rec['write_cycle']
            })
        return timeline
def get_ipc(self):
    """Calculate Instructions Per Cycle"""
    if self.total_cycles == 0:
        return 0
    return self.completed_instruction_count / self.total_cycles

def get_branch_prediction_accuracy(self):
    """Calculate branch prediction accuracy"""
    if self.total_branches == 0:
        return 1.0  # No branches, so 100% accuracy
    correct_predictions = self.total_branches - self.mispredictions
    return correct_predictions / self.total_branches

def get_statistics(self):
    """Return all performance statistics"""
    return {
        'ipc': self.get_ipc(),
        'total_instructions': self.completed_instruction_count,
        'total_cycles': self.total_cycles,
        'branch_accuracy': self.get_branch_prediction_accuracy(),
        'total_branches': self.total_branches,
        'mispredictions': self.mispredictions
    }
