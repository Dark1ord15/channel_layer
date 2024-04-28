import base64
from concurrent import futures
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import random
import requests as api

executor = futures.ThreadPoolExecutor(max_workers=10)

class CodeView(APIView):

    def post(self, request):
        # 0. Валидация данных
        try:
            data = request.data
            # Преобразование в байты
            payload = bytes(data['payload'], 'utf-8')
            print(payload)
            segment_number = int(data['segment_number'])
            total_segments = int(data['total_segments'])
            sender_name = data['sender_name']
            assert segment_number <= total_segments
            executor.submit(logic, payload, segment_number, total_segments, data['id'], sender_name)
            return Response(status=status.HTTP_200_OK)

        except (KeyError, AssertionError, ValueError, base64.binascii.Error) as e:
            return Response({"message": f"Invalid request: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


def logic(payload, segment_number, total_segments, id, sender_name):
    print('mew')
    # 1. Кодирование Хэмминга для 300 байт данных
    encoded_segment = hamming_encode_300_bytes(payload)
    print(len(payload))
    # 2. Вносим ошибку с вероятностью 10%
    if random.random() < 0.1:
        error_index = random.randint(0, len(encoded_segment) - 1)
        encoded_segment[error_index] = int(encoded_segment[error_index]) ^  0x01  # Простое инвертирование одного бита

    # 3. Декодирование, исправление ошибки
    decoded_segment, had_error = hamming_decode_300_bytes(encoded_segment)
    print(decoded_segment)
    # 4. Вероятность потерять сегмент - 2%
    if random.random() < 0.02:
        return

    api.post('http://127.0.0.1:8080/transfer', json={
        'id': id,
        'sender_name': sender_name,
        'segment_number': segment_number,
        'total_segments': total_segments,
        'payload': decoded_segment.decode('utf-8'),
        'had_error': had_error,
    })


def chunk_data(data, chunk_size):
    """Разделяет данные на блоки по chunk_size бит."""
    return [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

def combine_chunks(chunks):
    """Объединяет блоки данных в одну строку."""
    return ''.join(chunks)

# Теперь используем эти функции для кодирования и декодирования
def hamming_encode_300_bytes(data):
    # Преобразовать данные из байтов в биты
    bit_data = ''.join(f"{byte:08b}" for byte in data)
    # Разделяем данные на блоки по 4 бита
    blocks = chunk_data(bit_data, 4)
    # Применяем код Хэмминга на каждый блок
    encoded_blocks = [hamming_encode(block) for block in blocks]
    # Объединяем закодированные блоки обратно в одну строку бит
    encoded_bit_data = combine_chunks([''.join(map(str, block)) for block in encoded_blocks])
    print('encoded_bit_data', encoded_bit_data)
    # Преобразуем биты обратно в байты
    return encoded_bit_data

def hamming_decode_300_bytes(bit_data):
    # Разделяем данные на блоки по 7 бита (как в коде Хэмминга)
    blocks = chunk_data(bit_data, 7)
    # Если последний блок не равен 7 битам, отбрасываем его
    if len(blocks[-1])!= 7:
        blocks = blocks[:-1]
    # Применяем декодирование Хэмминга на каждый блок
    had_error = False
    decoded_blocks = []
    for block in blocks:
        code, error_pos = hamming_decode(block)
        decoded_blocks.append(code)
        had_error = had_error or error_pos != 0
    # Переводим каждый блок в строку
    decoded_bit_data = [''.join(map(str, block)) for block in decoded_blocks]
    # Объединяем декодированные блоки обратно в одну строку бит
    decoded_bit_data = combine_chunks(decoded_bit_data)
    # Преобразуем биты обратно в байты
    decoded_bytes_data = [int(decoded_bit_data[i:i+8], 2) for i in range(0, len(decoded_bit_data), 8)]
    return bytes(decoded_bytes_data), had_error

def hamming_encode(data):
    # Принимает 4-битный блок данных и возвращает 7-битный код Хэмминга
    d = [int(bit) for bit in data]
    # Рассчитываем контрольные биты
    p1 = d[0] ^ d[1] ^ d[3]
    p2 = d[0] ^ d[2] ^ d[3]
    p3 = d[1] ^ d[2] ^ d[3]
    # Возвращаем 7-битный код
    return [p1, p2, d[0], p3, d[1], d[2], d[3]]

def hamming_decode(code):
    # Принимает 7-битный код Хэмминга и возвращает 4-битные данные
    p = [int(bit) for bit in code]
    # Рассчитываем синдромы
    s1 = p[0] ^ p[2] ^ p[4] ^ p[6]
    s2 = p[1] ^ p[2] ^ p[5] ^ p[6]
    s3 = p[3] ^ p[4] ^ p[5] ^ p[6]
    # Вычисляем позицию ошибки (если есть)
    error_pos = s1 * 1 + s2 * 2 + s3 * 4
    if error_pos:
        # Исправляем ошибку, если она присутствует
        p[error_pos - 1] ^= 1
    # Возвращаем исходные данные
    return [p[2], p[4], p[5], p[6]], error_pos