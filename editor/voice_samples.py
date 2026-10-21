"""Read ten stock iterator clips from the user's game, without shipping audio.

The reader is deliberately limited to UnityFS PCM16 AudioClip resources. It does
not load assemblies, execute asset contents, accept arbitrary asset names, or
write extracted game data into projects. Unsupported formats fail explicitly.
"""
import functools
import io
from pathlib import Path
import struct
import wave

NAMES = {bank: tuple(prefix+str(i) for i in range(1, 6))
         for bank, prefix in [('pebbles', 'PebblesChat'), ('moon', 'MoonChat')]}
MAX_BLOCK = 16*1024*1024


def _read(stream, size):
    if size < 0 or size > MAX_BLOCK:
        raise ValueError('原版声音资源格式不受支持')
    data = stream.read(size)
    if len(data) != size:
        raise ValueError('原版声音资源不完整')
    return data


def _zstr(stream):
    data = bytearray()
    while len(data) < 1024:
        value = _read(stream, 1)
        if value == b'\0':
            return data.decode('utf-8')
        data.extend(value)
    raise ValueError('原版声音资源格式不受支持')


def _unpack(stream, fmt):
    return struct.unpack(fmt, _read(stream, struct.calcsize(fmt)))


def _inflate(data, length, flags):
    """Bounded raw LZ4 block decoder; UnityFS uses no frame wrapper."""
    mode = flags & 63
    if not 0 <= length <= MAX_BLOCK:
        raise ValueError('原版声音资源格式不受支持')
    if mode == 0:
        result = data
    elif mode in (2, 3):
        out = bytearray()
        pos = 0
        while pos < len(data):
            token = data[pos]; pos += 1
            literal = token >> 4
            if literal == 15:
                while True:
                    if pos >= len(data):raise ValueError('原版声音资源不完整')
                    extra = data[pos]; pos += 1; literal += extra
                    if extra != 255:break
            if pos+literal > len(data) or len(out)+literal > length:
                raise ValueError('原版声音资源不完整')
            out.extend(data[pos:pos+literal]); pos += literal
            if pos == len(data):break
            if pos+2 > len(data):raise ValueError('原版声音资源不完整')
            offset = data[pos] | data[pos+1] << 8; pos += 2
            if offset == 0 or offset > len(out):raise ValueError('原版声音资源不完整')
            match = (token & 15)+4
            if (token & 15) == 15:
                while True:
                    if pos >= len(data):raise ValueError('原版声音资源不完整')
                    extra = data[pos]; pos += 1; match += extra
                    if extra != 255:break
            if len(out)+match > length:raise ValueError('原版声音资源不完整')
            # Copying a repeated span handles overlapping LZ4 matches in bulk.
            repeat = bytes(out[-offset:])
            out.extend((repeat*((match+offset-1)//offset))[:match])
        result = bytes(out)
    else:
        raise ValueError('原版声音压缩格式不受支持')
    if len(result) != length:raise ValueError('原版声音资源不完整')
    return result


class Bundle:
    def __init__(self, path):
        self.path = path
        with path.open('rb') as stream:
            if _zstr(stream) != 'UnityFS':raise ValueError('原版声音资源格式不受支持')
            version, = _unpack(stream, '>I')
            _zstr(stream); engine = _zstr(stream)
            size, packed, expanded, flags = _unpack(stream, '>QIII')
            if version not in (6, 7, 8) or size != path.stat().st_size:
                raise ValueError('原版声音资源格式不受支持')
            # Unity 2019.4.15+ also aligns older-version headers to 16 bytes.
            if version >= 7 or engine.startswith('2019.4.') and int(engine.split('.')[2].split('f')[0]) >= 15:
                stream.seek((stream.tell()+15)//16*16)
            start = stream.tell()
            if flags & 128:stream.seek(size-packed)
            info = io.BytesIO(_inflate(_read(stream, packed), expanded, flags))
            data_start = start if flags & 128 else stream.tell()
            if flags & 512:data_start = (data_start+15)//16*16
            _read(info, 16); count, = _unpack(info, '>I')
            if count > 100000:raise ValueError('原版声音资源格式不受支持')
            self.blocks = []; plain = 0; physical = data_start
            for _ in range(count):
                raw, compressed, compression = _unpack(info, '>IIH')
                if raw > MAX_BLOCK or compressed > MAX_BLOCK or physical+compressed > size:
                    raise ValueError('原版声音资源格式不受支持')
                self.blocks.append((plain, raw, physical, compressed, compression))
                plain += raw; physical += compressed
            entries, = _unpack(info, '>I')
            if entries > 100:raise ValueError('原版声音资源格式不受支持')
            self.nodes = {}
            for _ in range(entries):
                offset, length, _flags = _unpack(info, '>QQI'); name = _zstr(info)
                if offset+length > plain:raise ValueError('原版声音资源不完整')
                self.nodes[name] = (offset, length)

    def span(self, start, size):
        if not 0 <= size <= MAX_BLOCK:raise ValueError('原版声音资源格式不受支持')
        chunks = []
        with self.path.open('rb') as stream:
            for base, length, offset, packed, flags in self.blocks:
                if base+length <= start or base >= start+size:continue
                stream.seek(offset)
                block = _inflate(_read(stream, packed), length, flags)
                chunks.append(block[max(0, start-base):min(length, start+size-base)])
        result = b''.join(chunks)
        if len(result) != size:raise ValueError('原版声音资源不完整')
        return result


def _clip_resource(bundle, name):
    # AudioClip names are serialized as a length-prefixed aligned string. Match
    # only the ten known names, then validate every following resource field.
    needle = struct.pack('<I', len(name))+name.encode('ascii')
    for node, (offset, length) in bundle.nodes.items():
        if node.endswith('.resource') or length > MAX_BLOCK:continue
        data = bundle.span(offset, length); pos = data.find(needle)
        while pos >= 0:
            try:
                reader = io.BytesIO(data); reader.seek((pos+len(needle)+3)//4*4)
                load, channels, frequency, bits, seconds = _unpack(reader, '<iiiif')
                if load not in (0, 1, 2) or channels not in (1, 2) or not 8000 <= frequency <= 192000 or bits != 16 or not 0 < seconds < 30:
                    raise ValueError('not an audio record')
                _read(reader, 4); _unpack(reader, '<i'); _read(reader, 4)
                size, = _unpack(reader, '<I')
                if size > 512:raise ValueError('not a resource path')
                resource = _read(reader, size).decode('utf-8'); reader.seek((reader.tell()+3)//4*4)
                start, size, compression = _unpack(reader, '<QQI')
                resource = resource.rsplit('/', 1)[-1]
                if compression != 0 or resource not in bundle.nodes:raise ValueError('not a PCM resource')
                base, total = bundle.nodes[resource]
                if start+size > total:raise ValueError('bad resource bounds')
                return bundle.span(base+start, size), channels, frequency
            except (ValueError, UnicodeError, struct.error):
                pos = data.find(needle, pos+1)
    raise ValueError('未找到原版迭代器音频，请检查游戏文件')


def _wave(raw, channels, frequency):
    if raw[:4] != b'FSB5' or len(raw) < 68:
        raise ValueError('原版声音压缩格式不受支持')
    version, count, headers, names, data_size, mode = struct.unpack_from('<6I', raw, 4)
    header_size = 60 if version == 1 else 64
    if version not in (0, 1) or count != 1 or mode != 2 or channels not in (1,2) or not 8000 <= frequency <= 192000:
        raise ValueError('原版声音压缩格式不受支持')
    if headers < 8 or len(raw) < header_size+headers:raise ValueError('原版声音资源不完整')
    sample_header, = struct.unpack_from('<Q', raw, header_size)
    frames = sample_header >> 34
    start = header_size+headers+names
    length = frames*channels*2
    if not 0 < length <= data_size or start+data_size > len(raw):
        raise ValueError('原版声音资源不完整')
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(frequency)
        wav.writeframes(raw[start:start+length])
    return output.getvalue()


@functools.lru_cache(maxsize=2)
def _bundle(path, modified, size):
    return Bundle(Path(path))


@functools.lru_cache(maxsize=10)
def _sample(path, modified, size, name):
    resource, channels, frequency = _clip_resource(_bundle(path, modified, size), name)
    return _wave(resource, channels, frequency)


def sample(game_root, bank, index):
    if bank not in NAMES or type(index) is not int or not 0 <= index < 5:
        raise ValueError('原版语音片段编号无效')
    path = Path(game_root)/'RainWorld_Data/StreamingAssets/AssetBundles/loadedsoundeffects'
    if not path.is_file():raise ValueError('未找到原版迭代器音频，请检查游戏路径')
    stat = path.stat()
    return _sample(str(path), stat.st_mtime_ns, stat.st_size, NAMES[bank][index])
