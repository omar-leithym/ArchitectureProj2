import backend
from RegisterManager import RegisterManager 

class ExecutionUnit:
    def __init__(self, fu_config=None):
        # Default configuration if none provided
        default_config = {
            'LOAD': {'cycles': 6, 'unit_count': 2},
            'STORE': {'cycles': 6, 'unit_count': 2},
            'ADD_SUB': {'cycles': 2, 'unit_count': 4},
            'MUL': {'cycles': 10, 'unit_count': 2},
            'NOR': {'cycles': 1, 'unit_count': 2},
            'BEQ': {'cycles': 1, 'unit_count': 2},
            'CALL_RET': {'cycles': 1, 'unit_count': 1}
        }
        
        # Use provided config or default
        config = fu_config if fu_config else default_config
        
        # Create individual functional units instead of a single entry per type
        self.functional_units = {}
        for fu_type, settings in config.items():
            self.functional_units[fu_type] = {
                'cycles': settings['cycles'],
                'units': [{'busy': False, 'instruction': None} for _ in range(settings['unit_count'])],
                'total_units': settings['unit_count']
            }

        # Track instructions in each stage
        self.waiting_to_execute_instructions = []
        self.executing_instructions = []
        self.completed_instructions = []
        self.instruction_history = []

        # Branch prediction and flush state
        self.prediction_state = "not_taken"  # Track current prediction
        self.branch_in_progress = False
        self.instructions_to_flush = []  # Track potentially wrong instructions

        # Cycle counter
        self.current_cycle = 0

    def issue_instruction(self, instruction, reg_manager):
        op = instruction['op'].upper()
        fu_type = self._get_functional_unit_type(op)

        # If branch is being processed, stall new instructions
        if self.branch_in_progress and fu_type not in ('BEQ', 'CALL_RET'):
            return False
        
        # Check if there's an available unit of this type
        fu_available = False
        unit_index = -1
        
        for i, unit in enumerate(self.functional_units[fu_type]['units']):
            if not unit['busy']:
                fu_available = True
                unit_index = i
                break
                
        if not fu_available:
            return False
            
        # Mark the unit as busy
        self.functional_units[fu_type]['units'][unit_index]['busy'] = True
        self.functional_units[fu_type]['units'][unit_index]['instruction'] = instruction

        # Mark destination register as busy
        if op not in ('STORE', 'BEQ', 'RET'):
            dest = instruction.get('dest_reg')
            if dest:
                # We catch KeyError if someone tries to mark R0 busy
                try:
                    reg_manager.set_busy(dest, f"{fu_type}_{unit_index}")
                except ValueError:
                    pass

        # Instruction record
        instr_record = {
            'instruction': instruction,
            'fu_type': fu_type,
            'fu_index': unit_index,
            'issue_cycle': self.current_cycle,
            'exec_start': None,
            'exec_end': None,
            'write_cycle': None
        }
        self.waiting_to_execute_instructions.append(instr_record)
        self.instruction_history.append(instr_record)  # Add to history

        if fu_type in ('BEQ', 'CALL_RET'):
            self.prediction_state = "not_taken"
            self.branch_in_progress = True
            self.instructions_to_flush = []  # Reset flush list
            
        return True
    
    def execute_process(self, reg_manager):
        self.current_cycle += 1
        
        # Check for completed branches
        for instr_record in list(self.executing_instructions):
            fu_type = instr_record['fu_type']
            if fu_type in ('BEQ', 'CALL_RET') and self.current_cycle >= instr_record['exec_end']:
                # Get actual branch outcome from backend
                actual_taken = backend.program_counter()
                # Handle misprediction
                if actual_taken != (self.prediction_state == "taken"):
                    self._flush_incorrect_instructions()
                self.branch_in_progress = False

        branch_executing = any(
            instr_record['fu_type'] in ('BEQ', 'CALL_RET') and 
            instr_record['exec_start'] is not None and 
            instr_record['exec_start'] <= self.current_cycle <= instr_record['exec_end']
            for instr_record in self.executing_instructions
        )
        if not branch_executing:
            self.branch_in_progress = False

        newly_started = []
        for instr_record in list(self.waiting_to_execute_instructions):
            op = instr_record['instruction']['op'].upper()

            # Check if operands are ready
            src_regs = instr_record['instruction'].get('src_regs', [])
            operands_ready = all(reg_manager.is_ready(r) for r in src_regs)
            
            if operands_ready and (not self.branch_in_progress or instr_record['fu_type'] in ('BEQ', 'CALL_RET')) and instr_record['exec_start'] is None:
                fu_type = instr_record['fu_type']
                cycles = self.functional_units[fu_type]['cycles']

                instr_record['exec_start'] = self.current_cycle
                instr_record['exec_end'] = self.current_cycle + cycles
                self.executing_instructions.append(instr_record)
                newly_started.append(instr_record)

        for rec in newly_started:
            self.waiting_to_execute_instructions.remove(rec)

        # Checking for completed instructions
        finished = []
        for instr_record in list(self.executing_instructions):
            if self.current_cycle >= instr_record['exec_end']:
                instr_record['write_cycle'] = self.current_cycle + 1
                self.completed_instructions.append(instr_record)
                finished.append(instr_record)
                
                # Free up that FU
                fu_type = instr_record['fu_type']
                fu_index = instr_record['fu_index']
                self.functional_units[fu_type]['units'][fu_index]['busy'] = False
                self.functional_units[fu_type]['units'][fu_index]['instruction'] = None

                # Once done, mark destination register ready (if any)
                dest = instr_record['instruction'].get('dest_reg')
                if dest:
                    reg_manager.set_ready(dest)

        for rec in finished:
            self.executing_instructions.remove(rec)

    def _flush_incorrect_instructions(self):
        """Remove all instructions issued after the branch"""
        # Clear functional units
        to_flush = set(self.instructions_to_flush)

        for fu_type in self.functional_units:
            for unit in self.functional_units[fu_type]['units']:
                if unit['busy'] and unit['instruction'] in to_flush:
                    unit['busy'] = False
                    unit['instruction'] = None
        
        # Remove from instruction_history (so timeline doesn't show flushed instrs)
        self.instruction_history = [
            i for i in self.instruction_history if i not in to_flush
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
            'completed': [i['instruction'] for i in self.completed_instructions]
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
