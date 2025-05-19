import backend as backend
class ExecutionUnit:
    def __init__(self):
        
        self.functional_units = {
            'LOAD': {'cycles': 6, 'busy': False, 'current_instruction': None},
            'STORE': {'cycles': 6, 'busy': False, 'current_instruction': None},
            'ADD': {'cycles': 2, 'busy': False, 'current_instruction': None},
            'SUB': {'cycles': 2, 'busy': False, 'current_instruction': None},
            'MUL': {'cycles': 10, 'busy': False, 'current_instruction': None},
            'NOR': {'cycles': 1, 'busy': False, 'current_instruction': None},
            'BEQ': {'cycles': 1, 'busy': False, 'current_instruction': None},
            'CALL_RET': {'cycles': 1, 'busy': False, 'current_instruction': None}
        }

        #track instructions in each stage
        self.waiting_to_execute_instructions = []
        self.executing_instructions = []
        self.completed_instructions = []
        self.instruction_history = []
        self.prediction_state = "not_taken"  # Track current prediction
        self.branch_in_progress = False
        self.instructions_to_flush = []  # Track potentially wrong instructions

        #cycle counter
        self.current_cycle =  0
        #branch busy flag
        #self.branch_busy = False 

    def issue_instruction(self, instruction, reg_manager):
        op = instruction['op'].upper()
        fu = self._get_functional_unit_type(op)

        # If branch is being processed, stall new instructions
        if self.branch_in_progress:
            return False
        
        #Check if functional unit is available

        if not self.functional_units[fu]['busy']:

            if op not in ('STORE', 'BEQ', 'RET'):
                try:
                    reg_manager.set_busy(instruction['dest_reg'], f"{fu}_0")
                except KeyError:
                    pass

        #Instruction record
                    instr_record = {
                'instruction': instruction,
                'fu_type': fu,
                'issue_cycle': self.current_cycle,
                'exec_start': None,
                'exec_end': None,
                'write_cycle': None
            }
            self.waiting_to_execute_instructions.append(instr_record)
            self.instruction_history.append(instr_record)  #Add to history
            self.functional_units[fu]['busy'] = True
            self.functional_units[fu]['current_instruction'] = instr_record

            if fu in ('BEQ', 'CALL_RET'):
                self.prediction_state = "not_taken"
                self.branch_in_progress = True
                self.instructions_to_flush = []  # Reset flush list
            return True
        return False
    
    def execute_process(self, reg_manager):
        self.current_cycle += 1

        # Check for completed branches
        for instr in list(self.executing_instructions):
            if instr['fu_type'] in ('BEQ', 'CALL_RET') and self.current_cycle >= instr['exec_end']:
                # Get actual branch outcome from backend
                actual_taken = backend.program_counter()  
                
                # Handle misprediction
                if actual_taken != (self.prediction_state == "taken"):
                    self._flush_incorrect_instructions()
                
                self.branch_in_progress = False

        branch_executing = any(
            instr['fu_type'] in ('BEQ', 'CALL_RET') and 
            instr['exec_start'] is not None and 
            self.current_cycle <= instr['exec_end']
            for instr in self.executing_instructions
        )

        if not branch_executing:
            self.branch_in_progress = False


        for instr in list(self.issue_instruction):
            op = instr['instruction']['op'].upper()

            # Check if operands are ready AND no branch is busy
            operands_ready = all(reg_manager.is_ready(reg)
                               for reg in instr['instruction'].get('src_regs', []))
            
            if operands_ready and not self.branch_in_progress == False and instr['exec_start'] is None:
                fu = self._get_functional_unit_type(op)
                cycles = self.functional_units[fu]['cycles']

                instr['exec_start'] = self.current_cycle
                instr['exec_end'] = self.current_cycle + cycles
                self.executing_instructions.append(instr)
                self.waiting_to_execute_instructions.remove(instr)


                #Checking for completed instructions

                for instr in list(self.executing_instructions):
                    if self.current_cycle >= instr['exec_end']:
                        instr['write_cycle'] = self.current_cycle + 1
                        self.completed_instructions.append(instr)
                        self.executing_instructions.remove(instr)

                        fu = instr['fu_type']
                        self.functional_units[fu]['busy'] = False
                        self.functional_units[fu]['current_instruction'] = None

                        if 'dest_reg' in instr['instruction']:
                            reg_manager.set_ready(instr['instruction']['dest_reg'])

    def _flush_incorrect_instructions(self):
        """Remove all instructions issued after the branch"""
        # Clear functional units
        for fu in self.functional_units.values():
            if fu['busy'] and fu['current_instruction'] in self.instructions_to_flush:
                fu['busy'] = False
                fu['current_instruction'] = None
        
        # Update instruction lists
        self.waiting_to_execute_instructions = [
            i for i in self.waiting_to_execute_instructions 
            if i not in self.instructions_to_flush
        ]
        self.instruction_history = [
            i for i in self.instruction_history 
            if i not in self.instructions_to_flush
        ]
        
        # Clear flush list
        self.instructions_to_flush = []

    def _get_functional_unit_type(self, op):

        if op in ('LOAD', 'STORE'):
            return op
        elif op in ('ADD', 'SUB'):
            return 'ADD' if op == 'ADD' else 'SUB'
        elif op in ('BEQ', 'CALL', 'RET'):
            return 'BEQ' if op == 'BEQ' else 'CALL_RET'
        else:
            return op #MUL, NOR
    
    def get_state(self):
        return{
                    'cycle': self.current_cycle,
            'issued': [i['instruction'] for i in self.waiting_to_execute_instructions],
            'executing': [(i['instruction'], f"Cycle {self.current_cycle - i['exec_start'] + 1}/{i['exec_end'] - i['exec_start']}")
                         for i in self.executing_instructions],
            'completed': self.completed_instructions 
        }

    def get_instruction_timeline(self):
        """
        Returns a list of all instructions with their timings.
        Format: [
            {
                'instruction': str,       # e.g., "ADD r1, r2, r3"
                'issue_cycle': int,       # Cycle issued
                'exec_start': int,        # Cycle execution started
                'exec_end': int,          # Cycle execution finished
                'write_cycle': int        # Cycle written back
            },
            ...
        ]
        """
        timeline = []
        for instr in self.instruction_history:
            # Convert instruction dict to a readable string (e.g., "ADD r1, r2, r3")
            op = instr['instruction']['op'].upper()
            src_regs = instr['instruction'].get('src_regs', [])
            dest_reg = instr['instruction'].get('dest_reg', '')
            offset = instr['instruction'].get('offset', '')

            if op in ('LOAD', 'STORE'):
                inst_str = f"{op} {dest_reg}, {offset}({src_regs[0]})"
            elif op in ('BEQ',):
                inst_str = f"{op} {src_regs[0]}, {src_regs[1]}, {offset}"
            elif op in ('CALL', 'RET'):
                inst_str = op
            else:
                inst_str = f"{op} {dest_reg}, {src_regs[0]}, {src_regs[1]}"

            timeline.append({
                'instruction': inst_str,
                'issue_cycle': instr['issue_cycle'],
                'exec_start': instr['exec_start'],
                'exec_end': instr['exec_end'],
                'write_cycle': instr['write_cycle']
            })
        return timeline