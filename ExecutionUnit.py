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

        #cycle counter
        self.current_cycle =  0

    def issue_instruction(self, instruction, reg_manager):
        op = instruction['op'].upper()
        fu = self._get_functional_unit_type(op)


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
            self.functional_units[fu]['busy'] = True
            self.functional_units[fu]['current_instruction'] = instr_record
            return True
        return False
    
    def execute_process(self, reg_manager):
        self.current_cycle += 1

        for instr in list(self.issue_instruction):
            op = instr['instruction']['op'].upper()

            #Check if operands are ready
            operands_ready = all(reg_manager.is_ready(reg)
                                for reg in instr['instruction'].get('src_regs', []))
            
            if operands_ready and instr['exec_start'] is None:
                fu = self._get_functional_unit_type(op)
                cycles = self.functional_units[fu]['cycles']

                instr['exec_start'] = self.current_cycle
                instr['exec_end'] = self.current_cycle + cycles
                self.executing_instructions.append(instr)
                self.waiting_to_execute_instructions.remove(instr)


                #Checking for completed instructions

                for instr in list(self.executing_instructions):
                    if self.current_cycle >= instr['exec_end']:
                        instr['write_cycle'] = self.current_cycle
                        self.completed_instructions.append(instr)
                        self.executing_instructions.remove(instr)

                        fu = instr['fu_type']
                        self.functional_units[fu]['busy'] = False
                        self.functional_units[fu]['current_instruction'] = None

                        if 'dest_reg' in instr['instruction']:
                            reg_manager.set_ready(instr['instruction']['dest_reg'])

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