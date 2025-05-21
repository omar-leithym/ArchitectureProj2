class RegisterManager:
    def __init__(self):
        self.registers = {
            'R0': {'value': 0, 'status': 'READY'},
            'R1': {'value': None, 'status': 'READY'},
            'R2': {'value': None, 'status': 'READY'},
            'R3': {'value': None, 'status': 'READY'},
            'R4': {'value': None, 'status': 'READY'},
            'R5': {'value': None, 'status': 'READY'},
            'R6': {'value': None, 'status': 'READY'},
            'R7': {'value': None, 'status': 'READY'}
        }

    def validate_register(self, reg_name):
        if not isinstance(reg_name, str) or reg_name.upper() not in self.registers:
            raise ValueError("Invalid register name: {reg_name}")
        return reg_name.upper()

    def is_ready(self, reg_name):
        reg = self.validate_register(reg_name)
        return self.registers[reg]['status'] == 'READY'

    def set_busy(self, reg_name, producer):
        # Reg is being written by a producer
        reg = self.validate_register(reg_name)
        if reg == 'R0':
            raise ValueError("Cannot write to R0")
        self.registers[reg]['status'] = producer

    def set_ready(self, reg_name):
        #Mark reg as ready when write is complete
        reg = self.validate_register(reg_name)
        self.registers[reg]['status'] = 'READY'
       # return self.registers[reg]['status']

    def get_status(self, reg_name):
        #Get current status

        reg = self.validate_register(reg_name)
        return self.registers[reg]['status']

    def __str__(self):
        """Printable register status"""
        return "\n".join(
            f"{reg}: {info['status']}"
            for reg, info in self.registers.items()
        )

