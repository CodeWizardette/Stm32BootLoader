#smtboo
import sys
import getopt
import serial
import time

try:
    from progressbar import *
    usepbar = 1
except ImportError:
    usepbar = 0
QUIET = 20
chip_ids = {
    0x412: "STM32 Düşük Yoğunluklu",
    0x410: "STM32 Orta Yoğunluklu",
    0x414: "STM32 Yüksek Yoğunluklu",
    0x420: "STM32 Orta Yoğunluklu Değer Hattı",
    0x428: "STM32 Yüksek Yoğunluklu Değer Hattı",
    0x430: "STM32 XL Yoğunluklu",
    0x416: "STM32 Orta Yoğunluklu Ultra Düşük Güç Hattı",
    0x411: "STM32F2xx",
    0x413: "STM32F4xx",
}

def mdebug(seviye, mesaj):
    if QUIET >= seviye:
        print(mesaj)

class CmdException(Exception):
    pass

class CommandInterface:
    extended_erase = 0

    def open(self, port='/dev/ttyUSB0', baudrate=115200):
        try:
            self.sp = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity=serial.PARITY_EVEN,
                stopbits=1,
                xonxoff=0,
                rtscts=0,
                timeout=5
            )
        except serial.SerialException as e:
            raise CmdException(f"Port açılamıyor: {e}")

    def _wait_for_ask(self, info=""):
        try:
            ask = ord(self.sp.read())
        except:
            raise CmdException("Port okunamıyor veya zaman aşımına uğradı")
        else:
            if ask == 0x79:
                return 1
            else:
                if ask == 0x1F:
                    raise CmdException("NACK " + info)
                else:
                    raise CmdException("Bilinmeyen yanıt. " + info + ": " + hex(ask))

    def reset(self):
        self.sp.setDTR(0)
        time.sleep(0.1)
        self.sp.setDTR(1)
        time.sleep(0.5)

    def initChip(self):
        self.sp.setRTS(0)
        self.reset()
        self.sp.write("\x7F")
        return self._wait_for_ask("Senkro")

    def releaseChip(self):
        self.sp.setRTS(1)
        self.reset()

    def cmdGeneric(self, cmd):
        self.sp.write(chr(cmd))
        self.sp.write(chr(cmd ^ 0xFF))
        return self._wait_for_ask(hex(cmd))

    def cmdReadMemory(self, addr, length):
        self.sp.write(chr(0x11))
        self.sp.write(chr(0xEE))
        self.sp.write(chr(0x11 ^ 0xFF))
        self.sp.write(chr(0xEE ^ 0xFF))
        self.sp.write(chr((addr >> 24) & 0xFF))
        self.sp.write(chr((addr >> 16) & 0xFF))
        self.sp.write(chr((addr >> 8) & 0xFF))
        self.sp.write(chr(addr & 0xFF))
        self.sp.write(chr((length - 1) & 0xFF))
        self.sp.write(chr(((length - 1) ^ 0xFF) & 0xFF))
        return self._wait_for_ask("Read Memory")

    def cmdWriteMemory(self, addr, data):
        self.sp.write(chr(0x31))
        self.sp.write(chr(0xCE))
        self.sp.write(chr(0x31 ^ 0xFF))
        self.sp.write(chr(0xCE ^ 0xFF))
        self.sp.write(chr((addr >> 24) & 0xFF))
        self.sp.write(chr((addr >> 16) & 0xFF))
        self.sp.write(chr((addr >> 8) & 0xFF))
        self.sp.write(chr(addr & 0xFF))
        self.sp.write(chr((len(data) - 1) & 0xFF))
        self.sp.write(chr(((len(data) - 1) ^ 0xFF) & 0xFF))
        for byte in data:
            self.sp.write(chr(byte))
        return self._wait_for_ask("Write Memory")

    # Diğer metodlar buraya ekleyin...

    def readMemory(self, addr, lng):
        data = []
        if usepbar:
            widgets = ['Okunuyor: ', Percentage(), ', ', ETA(), ' ', Bar()]
            pbar = ProgressBar(widgets=widgets, maxval=lng, term_width=79).start()

        while lng > 256:
            if usepbar:
                pbar.update(pbar.maxval - lng)
            else:
                mdebug(5, "Adresten %(len)d byte okunuyor: 0x%(addr)X" % {'addr': addr, 'len': 256})
            data += self.cmdReadMemory(addr, 256)
            addr += 256
            lng -= 256
        if usepbar:
            pbar.update(pbar.maxval - lng)
            pbar.finish()
        else:
            mdebug(5, "Adresten %(len)d byte okunuyor: 0x%(addr)X" % {'addr': addr, 'len': 256})
        data += self.cmdReadMemory(addr, lng)
        return data

    def writeMemory(self, addr, data):
        lng = len(data)
        if usepbar:
            widgets = ['Yazılıyor: ', Percentage(), ' ', ETA(), ' ', Bar()]
            pbar = ProgressBar(widgets=widgets, maxval=lng, term_width=79).start()

        offs = 0
        while lng > 256:
            if usepbar:
                pbar.update(pbar.maxval - lng)
            else:
                mdebug(5, "Adrese %(len)d byte yazılıyor: 0x%(addr)X" % {'addr': addr, 'len': 256})
            self.cmdWriteMemory(addr, data[offs:offs + 256])
            offs += 256
            addr += 256
            lng -= 256
        if usepbar:
            pbar.update(pbar.maxval - lng)
            pbar.finish()
        else:
            mdebug(5, "Adrese %(len)d byte yazılıyor: 0x%(addr)X" % {'addr': addr, 'len': 256})
        self.cmdWriteMemory(addr, data[offs:offs + lng] + ([0xFF] * (256 - lng)))


def usage():
    print(
        """Kullanım: %s [-hqVewvr] [-l uzunluk] [-p port] [-b baud] [-a addr] [-g addr] [dosya.bin]
    -h          Bu yardım
    -q          Sessiz mod
    -V          Ayrıntılı mod
    -e          Silme
    -w          Yazma
    -v          Doğrulama
    -r          Okuma
    -l uzunluk  Okuma uzunluğu
    -p port     Seri port (varsayılan: /dev/tty.usbserial-ftCYPMYJ)
    -b baud     Baud hızı (varsayılan: 115200)
    -a addr     Hedef adres
    -g addr     Çalıştırma adresi (genellikle 0x08000000)
    
    ./stm32loader.py -e -w -v example/main.bin
    
    """ % sys.argv[0]
    )


if __name__ == "__main__":

    # Psyco mevcutsa içe aktar
    try:
        import psyco
        psyco.full()
        print ("Psyco kullanılıyor...")
    except ImportError:
        pass

    conf = {
        'port': '/dev/ttyUSB0',
        'baud': 115200,
        'address': 0x08000000,
        'erase': 0,
        'write': 0,
        'verify': 0,
        'read': 0,
        'go_addr': -1,
    }

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hqVewvrp:b:a:l:g:")
    except getopt.GetoptError as err:
        print (str(err))
        usage()
        sys.exit(2)

    QUIET = 5

    for o, a in opts:
        if o == '-V':
            QUIET = 10
        elif o == '-q':
            QUIET = 0
        elif o == '-h':
            usage()
            sys.exit(0)
        elif o == '-e':
            conf['erase'] = 1
        elif o == '-w':
            conf['write'] = 1
        elif o == '-v':
            conf['verify'] = 1
        elif o == '-r':
            conf['read'] = 1
        elif o == '-p':
            conf['port'] = a
        elif o == '-b':
            conf['baud'] = eval(a)
        elif o == '-a':
            conf['address'] = eval(a)
        elif o == '-g':
            conf['go_addr'] = eval(a)
        elif o == '-l':
            conf['len'] = eval(a)
        else:
            assert False, "işlenmeyen seçenek"

    cmd = CommandInterface()
    try:
        cmd.open(conf['port'], conf['baud'])
    except CmdException as e:
        print(e)
        sys.exit(1)

    mdebug(10, "Port açık: %(port)s, baud: %(baud)d" % {'port': conf['port'], 'baud': conf['baud']})

    try:
        try:
            cmd.initChip()
        except CmdException:
            print("Başlatılamıyor. BOOT0'un etkin olduğundan ve cihazın sıfırlandığından emin olun")

        bootversion = cmd.cmdGeneric(0x00)
        mdebug(0, "Bootloader sürümü %X" % bootversion)

        id = cmd.cmdGeneric(0x02)
        mdebug(0, "Çip kimliği: 0x%x (%s)" % (id, chip_ids.get(id, "Bilinmeyen")))

        if conf['write'] or conf['verify']:
            data = list(map(lambda c: ord(c), open(args[0], 'rb').read()))

        if conf['erase']:
            cmd.cmdGeneric(0x43)

        if conf['write']:
            cmd.cmdGeneric(0x31)
            cmd._wait_for_ask("Write Enable")
            cmd.writeMemory(conf['address'], data)

        if conf['verify']:
            verify = cmd.readMemory(conf['address'], len(data))
            if data == verify:
                print("Doğrulama başarılı")
            else:
                print("Doğrulama BAŞARISIZ")
                print(str(len(data)) + ' vs ' + str(len(verify)))
                for i in range(0, len(data)):
                    if data[i] != verify[i]:
                        print(hex(i) + ': ' + hex(data[i]) + ' vs ' + hex(verify[i]))

        if not conf['write'] and conf['read']:
            rdata = cmd.readMemory(conf['address'], conf['len'])
            open(args[0], 'wb').write(''.join(map(chr, rdata)))

        if conf['go_addr'] != -1:
            cmd.cmdGeneric(0x21)
            cmd._wait_for_ask("Run")

    finally:
        cmd.releaseChip()
