class RegisterManager:
    def __init__(self):
        self.registers = {
            'R0': {'value': 0, 'status': 'READY'},   #R0 is always 0
            'R1': {'value': None, 'status': 'READY'},
            'R2': {'value': None, 'status': 'READY'},
            'R3': {'value': None, 'status': 'READY'},
            'R4': {'value': None, 'status': 'READY'},
            'R5': {'value': None, 'status': 'READY'},
            'R6': {'value': None, 'status': 'READY'},
            'R7': {'value': None, 'status': 'READY'}
        }
        # Keep a backup for branch misprediction recovery
        self.register_backup = self._copy_registers()

    def _copy_registers(self):
        """Create a deep copy of the registers state"""
        return {reg: {'value': info['value'], 'status': info['status']} 
                for reg, info in self.registers.items()}

    def backup_state(self):
        """Backup the current register state"""
        self.register_backup = self._copy_registers()

    def restore_state(self):
        """Restore from backup after branch misprediction"""
        self.registers = self._copy_registers()

    def validate_register(self, reg_name):
        if not isinstance(reg_name, str):
            raise ValueError(f"Invalid register name: {reg_name}")
        
        reg_upper = reg_name.upper()
        if reg_upper not in self.registers:
            raise ValueError(f"Invalid register name: {reg_name}")
        
        return reg_upper

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
        # Mark reg as ready when write is complete
        reg = self.validate_register(reg_name)
        self.registers[reg]['status'] = 'READY'

    def get_status(self, reg_name):
        # Get current status
        reg = self.validate_register(reg_name)
        return self.registers[reg]['status']
        
    def get_value(self, reg_name):
        # Get register value
        reg = self.validate_register(reg_name)
        return self.registers[reg]['value']
        
    def set_value(self, reg_name, value):
        # Set register value
        reg = self.validate_register(reg_name)
        if reg == 'R0':
            return  # R0 is always 0
        self.registers[reg]['value'] = value

    def __str__(self):
        """Printable register status"""
        return "\n".join(
            f"{reg}: {info['status']}"
            for reg, info in self.registers.items()
        )
