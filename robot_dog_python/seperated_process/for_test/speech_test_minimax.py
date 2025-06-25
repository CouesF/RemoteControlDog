import asyncio
import websockets
import json
import ssl
from pydub import AudioSegment  # 新增音频处理库
from pydub.playback import play
from io import BytesIO
import time


MODULE = "speech-02-hd"
EMOTION = "happy"


async def establish_connection(api_key):
    """建立WebSocket连接"""
    url = "wss://api.minimaxi.com/ws/v1/t2a_v2"
    headers = {"Authorization": f"Bearer {api_key}"}

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        ws = await websockets.connect(url, additional_headers=headers, ssl=ssl_context)
        connected = json.loads(await ws.recv())
        if connected.get("event") == "connected_success":
            print("连接成功")
            return ws
        return None
    except Exception as e:
        print(f"连接失败: {e}")
        return None


async def start_task(websocket, text):
    """发送任务开始请求"""
    start_msg = {
        "event": "task_start",
        "model": MODULE,
        "voice_setting": {
            "voice_id": "male-qn-qingse",
            "speed": 1,
            "vol": 1,
            "pitch": 0,
            "emotion": EMOTION
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1
        }
    }
    await websocket.send(json.dumps(start_msg))
    response = json.loads(await websocket.recv())
    return response.get("event") == "task_started"


async def continue_task(websocket, text):
    """发送继续请求并收集音频数据"""
    await websocket.send(json.dumps({
        "event": "task_continue",
        "text": text
    }))

    audio_chunks = []
    chunk_counter = 1  # 新增分块计数器
    while True:
        
        response = json.loads(await websocket.recv())
        if "data" in response and "audio" in response["data"]:
            audio = response["data"]["audio"]
            # 打印编码信息（前20字符 + 总长度）
            print(f"音频块 #{chunk_counter}")
            print(f"编码长度: {len(audio)} 字节")
            print(f"前20字符: {audio[:20]}...")
            print("-" * 40)

            audio_chunks.append(audio)
            chunk_counter += 1
        if response.get("is_final"):
            break
    return "".join(audio_chunks)


async def close_connection(websocket):
    """关闭连接"""
    if websocket:
        await websocket.send(json.dumps({"event": "task_finish"}))
        await websocket.close()
        print("连接已关闭")

async def main():
    API_KEY = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiLliJjkvbPpmLMiLCJVc2VyTmFtZSI6IuWImOS9s-mYsyIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxOTM2OTU2NDEzMjU1MzYxMDEwIiwiUGhvbmUiOiIxODc1NzMwNjI4NyIsIkdyb3VwSUQiOiIxOTM2OTU2NDEzMjUxMTY2NzA2IiwiUGFnZU5hbWUiOiIiLCJNYWlsIjoiIiwiQ3JlYXRlVGltZSI6IjIwMjUtMDYtMjQgMTM6Mzk6MjEiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.Y6-oqPQC7diMwIkcemeMCTDo4hM42IyGAcyG3UBSW3C1IWZBfs5h9n2gWTTABQRaajNdrYnGBjqaZMph3J70dHMFTO0G0mrnC5fl73pUH3HZa1svbMjp7rgnht4oTzld5LrKqR_WDPyrz6oJXZKo-PdozvcHO6f55YurCseZ_gA_BEpBbRueHqigHVabAGn3kzJuCM-p0TMfpdVgSuhw62Py54SO0FbZZPcpdV9RJEUNqXn2_NE2t1vaCV72ZckunDts8y025ON8NWSrxeqr1oP8XdIJGIAru3EObsVt13y6bv1UNmxV89JJnfBXY-_9rCZdyjQQ49lI3dSrgBCWXQ"  # 你的 API_KEY
    TEXT = "这是一个简化版的语音合成示例"

    t0 = time.time()
    ws = await establish_connection(API_KEY)
    if not ws:
        return
    t1 = time.time()

    try:
        if not await start_task(ws, TEXT[:10]):
            print("任务启动失败")
            return
        t2 = time.time()

        t3 = time.time()  # 准备发送文本
        hex_audio = await continue_task(ws, TEXT)
        t4 = time.time()  # 收到全部音频

        # 解码 + 播放
        audio_bytes = bytes.fromhex(hex_audio)
        with open("output.mp3", "wb") as f:
            f.write(audio_bytes)
        print("音频已保存为output.mp3")

        audio = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
        print("正在播放音频...")
        t5 = time.time()
        play(audio)
        t6 = time.time()

        print("\n📊 延迟统计（单位：秒）")
        print(f"连接建立耗时: {t1 - t0:.3f}")
        print(f"任务启动耗时: {t2 - t1:.3f}")
        print(f"发送文本至接收完毕耗时: {t4 - t3:.3f}")
        print(f"播放前解码耗时: {t5 - t4:.3f}")
        print(f"音频播放时长: {t6 - t5:.3f}")
        print(f"总耗时: {t6 - t0:.3f}")

    finally:
        await close_connection(ws)



if __name__ == "__main__":
    asyncio.run(main())