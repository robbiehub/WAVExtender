import sys
import mmap
import datetime
import enum
import shutil
import struct
import subprocess
import argparse
import os
import os.path

class WAVFile():
    def __init__(self, **kwargs):
        self.loop_start = None
        self.loop_end = None
        self.sample_rate = None
        self.sample_res = None
        self.channel_number = None
        self.data_size = None
        self.time_start = None
        self.time_end = None
        self.length = None
        self.compression_code = None
        self.output_path = None
        self.temp_path = None
        self.final_length = None
        
        self.path = kwargs.get("file", None).strip()
        self.get_info()

    def extend(self, *args, **kwargs):
        conv_type = int(kwargs.get("type", None))
        if conv_type is not None:
            n_times = 0
            self.output_path = kwargs.get("output", None).strip()

            # Agarrar los puntos de loopeo
            if(self.loop_start is None or self.loop_end is None):
                return

            if conv_type == 1:
                n_times = int(kwargs.get("times", 0))
                if n_times is None:
                    print("No number of loops specified.")
                    return
                loop_length = datetime.timedelta(seconds=(self.loop_end - self.loop_start)/self.sample_rate)
                self.final_length = datetime.timedelta(seconds=self.length + (loop_length.total_seconds() * n_times))
                print(f"Extend {n_times} times")
            
            if conv_type == 2:
                print("Extend by length")
                target_length = kwargs.get("length", None)
                if target_length is not None:
                    loop_length = datetime.timedelta(seconds=(self.loop_end - self.loop_start)/self.sample_rate)
                    target_length = datetime.timedelta(seconds=int(target_length))
                    total_length = datetime.timedelta(seconds=self.length)

                    if target_length >= loop_length:
                        while total_length < target_length:
                            n_times += 1
                            total_length += loop_length
                        self.final_length = total_length
                    else:
                        print("Target length is less than the file's length.")
                        return
                else:
                    print("No length specified.")
                    return
            
            print(f'Final length: {str(self.final_length.total_seconds())} seconds ({self.final_length})')
            # print(f'Length: {self.length} seconds ({datetime.timedelta(seconds=self.length)})')

            # Revisar compresion
            temp_path = self.output_path
            if self.compression_code != 1:
                print("File is compressed. Attempting decompression...")
                # Quitar compresion
                _, temp_path = self.decompress()
            else:
                filename = os.path.basename(self.output_path).split(".")[0] + "__temp.wav"
                temp_path = os.path.join(os.path.dirname(self.output_path), filename)
                shutil.copy2(self.path, temp_path)
            # Proceso de loopeado
            with open(temp_path, 'r+b') as source_file:
                data = mmap.mmap(source_file.fileno(), 0, access=mmap.ACCESS_WRITE)
                # Obtener el tamaño original
                data_offset = data.find(b'data')
                new_bytes_offset = None
                data.seek(data_offset + 4)
                size = int.from_bytes(data.read(4), "little")
                bytes_per_sample = int(self.channel_number * (self.sample_res/8))
                loop_start_from_data = self.loop_start * bytes_per_sample
                loop_end_from_data = self.loop_end * bytes_per_sample
                loop_size = loop_end_from_data - loop_start_from_data
                loop_pos = data_offset + 8 + loop_start_from_data
                loop_end_pos = data_offset + 8 + loop_end_from_data
                
                data.seek(loop_pos)
                loop_bytes = data.read(loop_size)

                data.seek(0,2)
                source_file.seek(data.tell()) # Ir al final
                # data.move(loop_end, loop_start_from_data, loop_size)

                # Ciclo para copiar el loop varias veces
                # Los bytes se van a copiar al final del archivo y luego se moveran a su lugar correspondiente
                if new_bytes_offset is None:
                    new_bytes_offset = data.tell()
                data.close()
                for n in range(0, n_times):
                    source_file.write(loop_bytes)
                    size += len(loop_bytes)
                
                source_file.flush()

                # Proceso para mover los bytes escritos
                data = mmap.mmap(source_file.fileno(), 0, access=mmap.ACCESS_WRITE)
                # Obtener los bytes que van a estar despues del loop
                af_size = new_bytes_offset - loop_end_pos
                data.seek(loop_end_pos)
                after_loop = data.read(af_size)
                # Mover los bytes del loop
                data.move(loop_end_pos, new_bytes_offset, len(loop_bytes) * n_times)
                # Restaurar los bytes que deben estar despues del loop
                data.seek(loop_end_pos + (len(loop_bytes) * n_times))
                data.write(after_loop)
                # Recalcular tamaños en los headers de RIFF y data
                data.seek(4)
                data.write(struct.pack("<I", data.size()))

                data.seek(data.find(b'data') + 4)
                data.write(struct.pack("<I", size))

                # Guardar cambios
                data.flush()
                data.close()
                source_file.close()
                
                print("Extension done.")

                extension = os.path.basename(self.output_path).split(".")[-1]
                if extension.lower() != "wav":
                    print(f"Converting to {extension}...")
                    self.conver()
                    os.remove(temp_path)
                else:
                    os.rename(temp_path, self.output_path)
                print("Finished.")

        else:
            print("No conversion type specified.")

    def get_info(self):
        """
        Función para analizar los posibles sample loops y al final obtener el punto de inicio y final
        Regresa una tupla con el siguiente formato en samples (<loop inicial>, <loop final>)
        """
        if self.path is not None:
            with open(self.path, 'r+b') as f:
                data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                fmt_offset = data.find(b'fmt')
                self.sample_rate = 0
                if fmt_offset != -1:
                    data.seek(fmt_offset + 8)
                    self.compression_code = int.from_bytes(data.read(2), "little")
                    self.channel_number = int.from_bytes(data.read(2), "little")
                    self.sample_rate = int.from_bytes(data.read(4), "little")
                    data.seek(6, 1)
                    self.sample_res = int.from_bytes(data.read(2), "little")
                    print(f"Sampling Rate: {self.sample_rate}")
                else:
                    print("File has no fmt header.")
                    return None
                # Obtener tamanio del wav
                data_offset = data.find(b'data')
                self.data_size = None
                if data_offset != -1:
                    data.seek(data_offset + 4)
                    self.data_size = int.from_bytes(data.read(4), "little")
                    print(f"WAV Size: {self.data_size}")
                else:
                    print("File has no data header.")
                    return None

                # Buscar offset del chunk de smpl
                data.seek(0)
                smpl_offset = data.find(b'smpl')
                if smpl_offset != -1:
                    # Nos vamos al offset encontrado y leemos cuantos loops tiene
                    data.seek(smpl_offset + 36)
                    print(f'# Sample loops: {int.from_bytes(data.read(4), "little")}')
                    print(f'# Sample data: {int.from_bytes(data.read(4), "little")}')
                    # Nos vamos al offset del primer loop y obtenemos los puntos de incio y final
                    loop_offset = data.tell()
                    data.seek(loop_offset + 8)
                    self.loop_start = int.from_bytes(data.read(4), "little")
                    self.loop_end = int.from_bytes(data.read(4), "little")
                    self.time_start = self.loop_start / self.sample_rate
                    self.time_end = self.loop_end / self.sample_rate
                    self.length = self.data_size / (self.sample_rate * self.channel_number * (self.sample_res/8))
                    print(f'Length: {self.length} seconds ({datetime.timedelta(seconds=self.length)})')
                    print(f'Loop start: {self.loop_start} samples ({datetime.timedelta(seconds=self.time_start)})')
                    print(f'Loop end: {self.loop_end} samples ({datetime.timedelta(seconds=self.time_end)})')

                    # Regresamos una tupla con los puntos encontrados
                    return (self.loop_start, self.loop_end, self.sample_rate, self.data_size)
                else:
                    print("File has no smpl chunk.")
                    return None
                data.close()
        else:
            print("File path is empty!")
            return None

    def decompress(self):
        filename = os.path.basename(self.output_path).split(".")[0] + "__temp.wav"
        save_path = os.path.join(os.path.dirname(self.output_path), filename)
        result = subprocess.run(["ffmpeg", "-loglevel", "16", "-y", "-i", self.path, save_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            print("Error decompressing file.")
        return (result.returncode == 0, save_path)

    def convert(self):
        filename = os.path.basename(self.output_path).split(".")[0] + "__temp.wav"
        ext_path = os.path.join(os.path.dirname(self.output_path), filename)
        result = subprocess.run(["ffmpeg", "-loglevel", "16", "-y", "-i", ext_path, "-af", "afade=out:st="+ str(self.final_length.total_seconds() - 3) +":d=3", self.output_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            print("Error converting file.")
            print(result)
        return result.returncode == 0

    def copy_headers(self, source_mmap, target_mmap):
        byte_headers = ""
        # RIFF
        riff_offset = source_mmap.find(b'RIFF')
        target_mmap.write(source_mmap.read(12))
        # fmt
        fmt_offset = source_mmap.find(b'fmt ')
        target_mmap.write(source_mmap.read(4))
        fmt_size = source_mmap.read(4)
        target_mmap.write(fmt_size)
        target_mmap.write(int.from_bytes(fmt_size, "little"))
        # smpl
        smpl_offset = source_mmap.find(b'smpl ')
        source_mmap.seek(smpl_offset)
        target_mmap.write(source_mmap.read(4))
        smpl_size = source_mmap.read(4)
        target_mmap.write(smpl_size)
        target_mmap.write(int.from_bytes(smpl_size, "little"))

        # Guardar cambios
        target_mmap.flush()
        source_mmap.seek(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-t", "--type", dest = "type", default = None, help="Extension Type (1 for N times and 2 for length)", required=True)
    parser.add_argument("-n", "--number", dest = "times", default = None, help="Number of loops. Only available when type equals 1.", required=False)
    parser.add_argument("-l", "--length", dest = "length", default = None, help="Desired length. Only available when type equals 2.", required=False)
    parser.add_argument("-i", "--input", dest = "input", default = None, help="Path to input file. Must be a .wav file.", required=True)
    parser.add_argument("-o", "--output", dest = "output", default = None, help="Where to save the extended file. Input file won't be modified.", required=True)

    args = parser.parse_args()

    print( "Type {} Times {} Length {} Input {} Output {} ".format(
        args.type,
        args.times,
        args.length,
        args.input,
        args.output
    ))

    wav = WAVFile(file = args.input)
    wav.extend(
        type = args.type,
        times = args.times,
        length = args.length,
        output = args.output
    )
