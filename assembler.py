import sys
import os

# Lookup tables for registers.
regtable = [['al', 'cl', 'dl', 'bl', 'ah', 'ch', 'dh', 'bh'],
            ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di']]

# Effective address calculation table for memory addressing modes.
eff_add_calc = ['bx + si', 'bx + di', 'bp + si', 'bp + di',
                'si', 'di', 'bp', 'bx']

def safe_read(f, num_bytes):
    data = f.read(num_bytes)
    return int.from_bytes(data, 'little') if data else None

# Decode register-to-register MOV instructions 
def dec_reg2reg(b1, b2):
    dflag = (b1 & 0b00000010) >> 1
    wflag = b1 & 0b00000001
    reg_field = (b2 & 0b00111000) >> 3
    rm_field  = b2 & 0b00000111
    op1 = regtable[wflag][reg_field]
    op2 = regtable[wflag][rm_field]
    opcode = (b1 & 0b11111100) >> 2
    if opcode == 0b100010:    
        return f"mov {op1 if dflag else op2}, {op2 if dflag else op1}"
    elif opcode == 0b000000:
        return f"add {op1 if dflag else op2}, {op2 if dflag else op1}"
    elif opcode == 0b001010:
        return f"sub {op1 if dflag else op2}, {op2 if dflag else op1}"
    elif opcode == 0b001110:
        return f"cmp {op1 if dflag else op2}, {op2 if dflag else op1}"
    else:
        return "Error: Invalid opcode"

# Decode immediate-to-register instructions (opcode 0xB0–0xBF)
def dec_i2reg(b1, b2, b3=None):                #For mov, s is set to 1, but for the new types like add, s can be either or, like d and w in other types
    wflag = (b1 & 0b00001000) >> 3
    reg = regtable[wflag][b1 & 0b00000111]
    if wflag == 0:
        # 8-bit immediate in b2.
        if b2 is None:
            return "Error: Missing immediate value"
        imm = b2
        if imm > 127:
            imm -= 256
    else:
        # 16-bit immediate: low byte in b2, high byte in b3.
        if b2 is None or b3 is None:
            return "Error: Missing immediate word"
        imm = (b3 << 8) | b2
        if imm > 32767:
            imm -= 65536
    return f"mov {reg}, {imm}"

def imm2reg_alt(b1, b2, b3, b4=None, b5=None):
    wflag = (b1 & 0b00000001)
    sflag = (b1 & 0b00000010) >> 1
    instruction_code = (b2 & 0b00111000) >> 3
    rm = b2 & 0b00000111
    mod = (b2 & 0b11000000) >> 6
    
    instruction = {0b000: "add", 0b101: "sub", 0b111: "cmp"}.get(instruction_code, "Error")
    if instruction == "Error":
        return "Error: Invalid instruction code"
    
    if mod == 0b11:
        dest = regtable[wflag][rm]
    elif mod == 0b00:
        dest = f"byte [{eff_add_calc[rm]}]"
    else:
        dest = eff_add_calc[rm] 
    
    if mod in [0b01, 0b10]:
        displacement = b3 if mod == 0b01 else (b4 << 8) | b3
        if displacement > 127 and mod == 0b01:
            displacement -= 256
        if displacement > 32767 and mod == 0b10:
            displacement -= 65536
        dest = f"word [{dest} + {displacement}]" if wflag else f"byte [{dest} + {displacement}]"
        imm = b4 if mod == 0b01 and b5 == None else b5
        instr_size = 4 if mod == 0b01 else 5
    else:
        imm = b3
        instr_size = 3
    
    return f"{instruction} {dest}, {imm}", instr_size

def imm2acc(b1, b2, b3=None):
    wflag = (b1 & 0b00000001)
    
    dest = regtable[wflag][0] 
    
    opcode = (b1 & 0b11111110) >> 1
    
    if opcode == 0b0000010:
        instruction = "add"
    elif opcode == 0b0010110:
        instruction = "sub"
    else:
        instruction = "cmp"
    
    if opcode == 0b0000010 or 0b0010110:
        if wflag == 0:
            # 8-bit immediate in b2.
            if b2 is None:
                return "Error: Missing immediate value"
            imm = b2
            if imm > 127:
                imm -= 256
        else:
            # 16-bit immediate: low byte in b2, high byte in b3.
            if b2 is None or b3 is None:
                return "Error: Missing immediate word"
            imm = (b3 << 8) | b2
            if imm > 32767:
                imm -= 65536
    else:
        imm = b2
    return f"{instruction} {dest}, {imm}"
        
    
    
    
            
    
    

# Decode MOV instructions that use memory addressing (opcodes 0x88–0x8B with mod != 11)
def dec_modrm_instr(b1, b2, b3=None, b4=None):
    dflag = (b1 & 0b00000010) >> 1  # Direction flag - CORRECTED: from b1
    wflag = b1 & 0b00000001         # Word flag (0 = 8-bit, 1 = 16-bit)
    reg_field = (b2 & 0b00111000) >> 3
    rm = b2 & 0b00000111
    mod = (b2 & 0b11000000) >> 6

    op1 = regtable[wflag][reg_field]  # First operand (register)

    # Determine instruction type (add, sub, cmp) - Simplified
    opcode = (b1 & 0b11111100) >> 2
    if opcode == 0b000000:
        instruction = "add"
    elif opcode == 0b001010:
        instruction = "sub"
    elif opcode == 0b001110:
        instruction = "cmp"
    else:
        return "Error: Invalid opcode"

    # Effective Address Calculation
    if mod == 0b00:
        if rm == 0b110:
            if b3 is None or b4 is None:
                return "Error: Missing direct address bytes"
            addr = (b4 << 8) | b3
            ea = f"[0x{addr:04x}]"
        else:
            ea = f"[{eff_add_calc[rm]}]"
    elif mod == 0b01:
        if b3 is None:
            return "Error: Missing 8-bit displacement"
        disp = b3 if b3 < 128 else b3 - 256
        ea = f"[{eff_add_calc[rm]} + {disp}]"
    elif mod == 0b10:
        if b3 is None or b4 is None:
            return "Error: Missing 16-bit displacement"
        disp = (b4 << 8) | b3
        if disp > 32767:
            disp -= 65536
        ea = f"{eff_add_calc[rm]} + {disp}"
    else:
        # mod == 0b11 (register addressing) should be handled elsewhere
        return "Error: mod=3 (register addressing) should be handled elsewhere"


    return f"{instruction} {op1 if dflag else ea}, {ea if dflag else op1}"

# Main disassembly function.
def disassemble(filename):
    with open(filename, 'rb') as f:
        byte_list = list(f.read())

    i = 0
    while i < len(byte_list):
        b1 = byte_list[i]
        print(f"\nProcessing byte {b1:08b} at index {i}")  # Debugging

        # Check for Register-to-Register or Register-to-Memory/Effective Address instructions
        if (b1 & 0b11111100) >> 2 in [0b000000, 0b001010, 0b001110]:  # ADD, SUB, CMP
            if i + 1 >= len(byte_list):
                print("Error: Missing MODRM byte")
                break
            b2 = byte_list[i + 1]
            mod = (b2 & 0b11000000) >> 6
            rm = b2 & 0b00000111
            displacement_size = 0

            if mod == 0b11:  # Register-to-register (mod == 11)
                print("Using: dec_reg2reg()")  # Debugging
                instr = dec_reg2reg(b1, b2)
                instr_size = 2
            else:  # Register-to-memory/Effective Address
                if mod == 0b00 and rm == 0b110:
                    displacement_size = 2  # 16-bit displacement
                elif mod == 0b01:
                    displacement_size = 1  # 8-bit displacement
                elif mod == 0b10:
                    displacement_size = 2  # 16-bit displacement

                b3 = byte_list[i + 2] if i + 2 < len(byte_list) else None
                b4 = byte_list[i + 3] if i + 3 < len(byte_list) else None
                print("Using: dec_modrm_instr()")  # Debugging
                instr = dec_modrm_instr(b1, b2, b3, b4)
                instr_size = 2 + displacement_size  # Move forward by correct instruction length

            used_bytes = byte_list[i:i+instr_size]
            print(f"Decoded: {instr} (bytes: {' '.join(f'{x:08b}' for x in used_bytes)})")
            i += instr_size
            continue

        # Immediate-to-Register (MOV, ADD, SUB, CMP)
        elif (b1 & 0b11111100) >> 2 == 0b100000:  # Immediate-to-register
            b2 = byte_list[i + 1] if i + 1 < len(byte_list) else None
            b3 = byte_list[i + 2] if i + 2 < len(byte_list) else None
            b4 = byte_list[i + 3] if i + 3 < len(byte_list) else None
            b5 = byte_list[i + 4] if i + 4 < len(byte_list) else None
            print("Using: imm2reg_alt()")  # Debugging
            instr, instr_size = imm2reg_alt(b1, b2, b3, b4, b5)  
            
            used_bytes = byte_list[i:i+instr_size]
            print(f"Decoded: {instr} (bytes: {' '.join(f'{x:08b}' for x in used_bytes)})")
            i += instr_size
            continue
        
        elif (b1 & 0b11111110) >> 1 in [0b0000010, 0b0010110, 0b0011110]:
            wflag = (b1 & 0b00000001)
            b2 = byte_list[i + 1] if i + 1 < len(byte_list) else None
            b3 = byte_list[i + 2] if i + 2 < len(byte_list) else None
            
            instr_size = 3 if wflag else 2
            print("Using: imm2acc()")
            instr = imm2acc(b1, b2, b3)
            
            used_bytes = byte_list[i:i+instr_size]
            print(f"Decoded: {instr} (bytes: {' '.join(f'{x:08b}' for x in used_bytes)})")
            i += instr_size
            continue
            
        else:
            print(f"⚠️ Unknown opcode: {b1:08b} at index {i}")
            i += 1 
def main():
    if len(sys.argv) != 3 or sys.argv[1] != '-d':
        print("Usage: python script.py -d filename")
        sys.exit(1)
    
    filename = sys.argv[2]
    if not os.path.isfile(filename):
        print(f"Error: File '{filename}' not found.")
        sys.exit(1)
    
    disassemble(filename)

if __name__ == '__main__':
    main()

