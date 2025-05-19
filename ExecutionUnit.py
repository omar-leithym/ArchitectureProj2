import backend
from RegisterManager import RegisterManager 
class ExecutionUnit:
    def __init__(self):
        
        self.functional_units = {
            'LOAD': {'cycles': 6, 'busy': False, 'current_instruction': None, 'unit_count': 2},
            'STORE': {'cycles': 6, 'busy': False, 'current_instruction': None, 'unit_count': 2},
            'ADD_SUB': {'cycles': 2, 'busy': False, 'current_instruction': None, 'unit_count': 4},
            'MUL': {'cycles': 10, 'busy': False, 'current_instruction': None, 'unit_count': 2},
            'NOR': {'cycles': 1, 'busy': False, 'current_instruction': None, 'unit_count': 2},
            'BEQ': {'cycles': 1, 'busy': False, 'current_instruction': None, 'unit_count': 2},
            'CALL_RET': {'cycles': 1, 'busy': False, 'current_instruction': None, 'unit_count': 1}
        }

        #track instructions in each stage
        self.waiting_to_execute_instructions = []
        self.executing_instructions = []
        self.completed_instructions = []
        self.instruction_history = []

        #Branch prediction and flush state
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
        
        if self.functional_units[fu]['unit_count'] > 0 and not self.functional_units[fu]['busy']:
            self.functional_units[fu]['unit_count'] -= 1
            self.functional_units[fu]['busy'] = True
        else:
            return False
        #Check if functional unit is available

        if op not in ('STORE', 'BEQ', 'RET'):
            dest = instruction.get('dest_reg')
            if dest:
                # We catch KeyError if someone tries to mark R0 busy
                try:
                    reg_manager.set_busy(dest, f"{fu}_0")
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
        #self.functional_units[fu]['busy'] = True
        #self.functional_units[fu]['current_instruction'] = instr_record

        if fu in ('BEQ', 'CALL_RET'):
            self.prediction_state = "not_taken"
            self.branch_in_progress = True
            self.instructions_to_flush = []  # Reset flush list
        return True
        return False
    
    def execute_process(self, reg_manager):
        if backend.step_mode:
            self.current_cycle += 1
        print("THE Cycle is:", self.current_cycle)
        # Check for completed branches
        for instr_record in list(self.executing_instructions):
            if fu in ('BEQ', 'CALL_RET') and self.current_cycle >= instr_record['exec_end']:
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

            # Check if operands are ready AND no branch is busy
            src_regs = instr_record['instruction'].get('src_regs', [])
            operands_ready = all(reg_manager.is_ready(r)
                            for r in src_regs)
            
            if operands_ready and not self.branch_in_progress == False and instr_record['exec_start'] is None:
                fu = instr_record['fu_type']
                cycles = self.functional_units[fu]['cycles']

                instr_record['exec_start'] = self.current_cycle
                instr_record['exec_end'] = self.current_cycle + cycles
                self.executing_instructions.append(instr_record)
                #self.waiting_to_execute_instructions.remove(instr)
                newly_started.append(instr_record)

                for rec in newly_started:
                    self.waiting_to_execute_instructions.remove(rec)
                #Checking for completed instructions

                finished = []
                for instr_record in list(self.executing_instructions):
                    if self.current_cycle >= instr_record['exec_end']:
                        instr_record['write_cycle'] = self.current_cycle + 1
                        self.completed_instructions.append(instr_record)
                        finished.append(instr_record)
                        #self.executing_instructions.remove(instr_record)
                        #self.functional_units[instr['fu_type']]['busy'] = False
                # Free up that FU
                fu = instr_record['fu_type']
                self.functional_units[fu]['busy'] = False
                self.functional_units[fu]['unit_count'] += 1

                # Once done, mark destination register ready (if any)
                dest = instr_record['instruction'].get('dest_reg')
                if dest:
                    reg_manager.set_ready(dest)

            # for rec in finished:
            #     self.executing_instructions.remove(rec)
            # if not self.functional_units[fu]['busy']:
            #     # Mark execution start
            #     instr['exec_start'] = self.current_cycle
            #     instr['exec_end'] = self.current_cycle + self.functional_units[fu]['cycles']
            #     self.executing_instructions.append(instr)
            #     self.waiting_to_execute_instructions.remove(instr)
            #     self.functional_units[fu]['busy'] = True

            # if 'dest_reg' in instr['instruction']:
            #     reg_manager.set_ready(instr['instruction']['dest_reg'])

    def _flush_incorrect_instructions(self):
        """Remove all instructions issued after the branch"""
        # Clear functional units
        to_flush = set(self.instructions_to_flush)

        for fu in self.functional_units.values():
            if fu['busy'] and fu['current_instruction'] in to_flush:
                fu['busy'] = False
                fu['current_instruction'] = None
                fu['unit_count'] +=1
        
        # Remove from instruction_history (so timeline doesn’t show flushed instrs)
        self.instruction_history = [
            i for i in self.instruction_history if i not in to_flush
        ]
        # Clear the flush set for next branch
        self.instructions_to_flush = []

        # # Update instruction lists
        # self.waiting_to_execute_instructions = [
        #     i for i in self.waiting_to_execute_instructions 
        #     if i not in self.instructions_to_flush
        # ]
        # self.instruction_history = [
        #     i for i in self.instruction_history 
        #     if i not in self.instructions_to_flush
        # ]
        
        # # Clear flush list
        # self.instructions_to_flush = []

    def _get_functional_unit_type(self, op):

        if op in ('LOAD', 'STORE'):
            return op
        elif op in ('ADD', 'SUB'):
            return 'ADD_SUB'
        elif op in ('BEQ', 'CALL', 'RET'):
            return 'BEQ' if op == 'BEQ' else 'CALL_RET'
        else:
            return op #MUL, NOR
    
    def get_state(self):
        """
        Return a snapshot of the current cycle, plus what’s waiting, executing, and completed.
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

    # def _format_instruction(self, instr):
    #     """
    #     Helper to turn an instruction‐dict into a human‐readable string for the timeline table.
    #     """
    #     op = instr['op'].upper()
    #     parts = []
    #     if op in ('LOAD', 'STORE'):
    #         parts.append(f"{instr['dest_reg']}, {instr['offset']}({instr['src_regs'][0]})")
    #     elif op == 'BEQ':
    #         parts.append(f"{instr['src_regs'][0]}, {instr['src_regs'][1]}, {instr['offset']}")
    #     elif op in ('CALL', 'RET'):
    #         pass
    #     else:
    #         parts.append(f"{instr['dest_reg']}, {instr['src_regs'][0]}, {instr['src_regs'][1]}")
    #     return f"{op} {' '.join(parts)}"
    def get_instruction_timeline(self):
        timeline = []
        print("I am inside the timeline function")
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
