"""
WebSocket Endpoints Router
所有 WebSocket 連線端點
"""

import asyncio
import base64
import logging
import os
import tempfile
from typing import TYPE_CHECKING

import cv2
import numpy as np
from ..services.rps_game_service import GameState, RPSGesture
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from ..services.rps_game_service import RPSGameService
    from ..services.status_broadcaster import StatusBroadcaster
    from ..services.emotion_service import EmotionService
    from ..services.drawing_service import DrawingService

logger = logging.getLogger(__name__)

# 創建 router
router = APIRouter(tags=["WebSocket"])

# 全域變數（會在 app.py 中設定）
rps_game_service: 'RPSGameService' = None
status_broadcaster: 'StatusBroadcaster' = None
emotion_service: 'EmotionService' = None
drawing_service: 'DrawingService' = None


def init_router(
    rps_service: 'RPSGameService',
    broadcaster: 'StatusBroadcaster',
    emotion_svc: 'EmotionService',
    drawing_svc: 'DrawingService'
):
    """初始化 router，注入 services"""
    global rps_game_service, status_broadcaster, emotion_service, drawing_service
    rps_game_service = rps_service
    status_broadcaster = broadcaster
    emotion_service = emotion_svc
    drawing_service = drawing_svc


@router.websocket("/ws/rps")
async def websocket_rps(websocket: WebSocket) -> None:
    """
    🎮 整合式 RPS WebSocket 端點（單一連接處理所有功能）

    整合式設計：單一 WebSocket 同時處理遊戲控制、影像串流辨識和狀態廣播
    優勢：開發者只需連線一個端點，簡化實作並提升效能

    主要功能：
    1. 🎯 即時手勢辨識：接收攝影機影像幀，進行 MediaPipe 手勢辨識
    2. 🎮 遊戲控制：處理開始/停止遊戲、提交手勢等控制指令
    3. 📡 狀態廣播：即時推送遊戲狀態更新（倒數、結果等）
    4. 🤖 自動手勢設定：信心度 > 60% 時自動設定玩家手勢

    客戶端發送訊息格式:
    - 心跳保活: {"type": "ping"}
    - 遊戲控制: {"type": "game_control", "action": "start_game", "target_score": 3}
    - 影像串流: {"type": "frame", "image": "data:image/jpeg;base64,...", "timestamp": 123.45}

    服務器回應訊息格式:
    - 辨識結果: {"type": "recognition_result", "gesture": "rock", "confidence": 0.96, "is_valid": true}
    - 控制確認: {"type": "control_ack", "action": "start_game", "status": "started"}
    - 遊戲狀態: {"type": "game_state", "stage": "countdown", "message": "3", "data": {...}}
    - 錯誤訊息: {"type": "error", "message": "辨識失敗"}
    - 心跳回應: {"type": "pong"}

    工作流程：
    1. 客戶端連接 WebSocket
    2. 發送 game_control 開始遊戲
    3. 持續發送 frame 進行即時辨識
    4. 後端自動設定高信心度手勢
    5. 遊戲狀態透過廣播即時更新

    Args:
        websocket (WebSocket): WebSocket 連接實例

    Note:
        整合式設計大幅簡化了前端實作，開發者不再需要管理多個 WebSocket 連接
    """
    await websocket.accept()
    logger.info("✅ RPS 整合式連接已建立")

    # 註冊接收遊戲狀態廣播
    queue = await status_broadcaster.register()

    try:
        while True:
            # 使用 asyncio.wait 同時等待兩種訊息來源
            receive_task = asyncio.create_task(websocket.receive_json())
            broadcast_task = asyncio.create_task(queue.get())

            done, pending = await asyncio.wait(
                [receive_task, broadcast_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # 取消未完成的任務
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # 處理完成的任務
            for task in done:
                # 檢查任務是否因為 disconnect 而失敗
                if task.exception() is not None:
                    exc = task.exception()
                    if isinstance(exc, (RuntimeError, WebSocketDisconnect)):
                        if "disconnect" in str(exc).lower() or "not connected" in str(exc).lower():
                            logger.info("WebSocket 連接已斷開")
                            raise WebSocketDisconnect()
                    # 如果是 broadcast_task 的錯誤，不要繼續循環
                    if task == broadcast_task:
                        logger.warning("廣播任務出錯: %s (可能連接已斷開)", exc)
                        raise WebSocketDisconnect()
                    logger.exception("任務執行錯誤: %s", exc)
                    continue

                try:
                    result = task.result()

                    # 如果是來自客戶端的訊息（receive_json）
                    if task == receive_task:
                        message_type = result.get("type", "")
                        logger.info("[RPS WS] 收到訊息類型: %s", message_type)

                        # 處理心跳
                        if message_type == "ping":
                            await websocket.send_json({"type": "pong"})
                            continue

                        # 處理影像幀辨識
                        if message_type == "frame":
                            image_data = result.get("image", "")
                            timestamp = result.get("timestamp", 0)

                            try:
                                # 處理 base64 影像
                                if image_data.startswith("data:image/"):
                                    image_data = image_data.split(",")[1]

                                image_bytes = base64.b64decode(image_data)
                                nparr = np.frombuffer(image_bytes, np.uint8)
                                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                                if img is None:
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": "無法解碼圖片"
                                    })
                                    continue

                                # MediaPipe 手勢辨識
                                gesture, confidence = rps_game_service.detector.detect(img)

                                # 🎯 自動設定玩家手勢（遊戲等待中 + 有效手勢 + 信心度 > 60%）
                                logger.info("[RPS WS] 遊戲狀態檢查: game_state=%s, gesture=%s, confidence=%.1f%%, player_gesture=%s",
                                           rps_game_service.game_state.value if rps_game_service.game_state else "None",
                                           gesture.value,
                                           confidence * 100,
                                           rps_game_service.player_gesture.value if rps_game_service.player_gesture else "None")

                                if (rps_game_service.game_state == GameState.WAITING_PLAYER and
                                    gesture != RPSGesture.UNKNOWN and
                                    confidence > 0.6 and
                                    rps_game_service.player_gesture is None):

                                    rps_game_service.player_gesture = gesture
                                    logger.info("✅ 自動設定玩家手勢: %s (%.1f%%)", gesture.value, confidence * 100)

                                # 發送辨識結果
                                await websocket.send_json({
                                    "type": "recognition_result",
                                    "gesture": gesture.value,
                                    "confidence": float(confidence),
                                    "timestamp": timestamp,
                                    "is_valid": gesture.value != "unknown"
                                })

                            except Exception as e:
                                logger.exception("影像辨識錯誤: %s", e)
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"影像辨識錯誤: {str(e)}"
                                })

                        elif message_type == "game_control":
                            action = result.get("action")
                            if action == "start_game":
                                target_score = result.get("target_score", 1)
                                try:
                                    start_result = rps_game_service.start_game(target_score)
                                    logger.info("[RPS WS] start_game 控制請求 (target=%s): %s", target_score, start_result)
                                    await websocket.send_json({
                                        "type": "control_ack",
                                        "action": action,
                                        **start_result
                                    })
                                except Exception as exc:
                                    logger.exception("啟動遊戲錯誤: %s", exc)
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": f"啟動遊戲失敗: {str(exc)}"
                                    })

                            elif action == "stop_game":
                                stop_result = rps_game_service.stop_game()
                                logger.info("[RPS WS] stop_game 控制請求: %s", stop_result)
                                await websocket.send_json({
                                    "type": "control_ack",
                                    "action": action,
                                    **stop_result
                                })

                            else:
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"未知的遊戲控制指令: {action}"
                                })

                        elif message_type == "no_gesture_detected":
                            # 處理「未偵測到手勢」的情況
                            unknown_confidence = float(result.get("unknown_confidence", 0))
                            logger.info("[RPS WS] 未偵測到有效手勢，unknown 信心度: %.1f%%", unknown_confidence * 100)

                            # 設定玩家手勢為 UNKNOWN（讓遊戲可以繼續）
                            if rps_game_service.game_state == GameState.WAITING_PLAYER:
                                rps_game_service.player_gesture = RPSGesture.UNKNOWN
                                logger.info("✅ 設定玩家手勢為 UNKNOWN，遊戲繼續")

                            await websocket.send_json({
                                "type": "gesture_set",
                                "gesture": "unknown",
                                "message": "未偵測到手勢，遊戲繼續"
                            })

                        else:
                            # 不支援的訊息類型
                            await websocket.send_json({
                                "type": "error",
                                "message": f"不支援的訊息類型: {message_type}"
                            })

                    # 如果是來自廣播的遊戲狀態更新
                    elif task == broadcast_task:
                        if result.get("channel") == "rps_game":
                            # 修改訊息類型為 game_state，但保留 channel 資訊
                            game_message = result.copy()
                            game_message["type"] = "game_state"
                            # 確保 channel 資訊被保留
                            if "channel" not in game_message:
                                game_message["channel"] = "rps_game"
                            logger.debug("[RPS WS] 推播遊戲狀態: %s", game_message.get("stage"))
                            await websocket.send_json(game_message)

                except (RuntimeError, WebSocketDisconnect) as e:
                    if "disconnect" in str(e).lower() or "WebSocket is not connected" in str(e):
                        logger.info("WebSocket 連接已斷開，停止處理訊息")
                        raise WebSocketDisconnect()
                    else:
                        logger.exception("處理訊息錯誤: %s", e)
                except Exception as e:
                    logger.exception("處理訊息錯誤: %s", e)

    except WebSocketDisconnect:
        logger.info("❌ RPS 整合式連接已斷開")
    except Exception as e:
        logger.exception("WebSocket 錯誤: %s", e)
    finally:
        await status_broadcaster.unregister(queue)
        logger.info("🔌 RPS 整合式連接關閉")


@router.websocket("/ws/gesture")
async def websocket_gesture(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time hand gesture updates.

    Establishes a persistent WebSocket connection to stream hand gesture
    detection results in real-time. Clients receive live updates as gestures
    are detected from camera feeds.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Note:
        Connection automatically handles cleanup on client disconnect.
        Only gesture-related messages are forwarded to this endpoint.
    """
    await websocket.accept()
    queue = await status_broadcaster.register()
    try:
        while True:
            message = await queue.get()
            if message.get("channel") == "gesture":
                await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        await status_broadcaster.unregister(queue)


@router.websocket("/ws/drawing")
async def websocket_drawing_gesture(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time gesture-based drawing.

    Handles interactive gesture drawing where users can draw on a virtual canvas
    using hand gestures detected from camera frames. Processes camera frames in
    real-time to detect finger positions and translate them into drawing actions.

    Supported message types:
    - Client → Server:
        - {"type": "open", "client_id": "unique_id"} - Open WebSocket connection
        - {"type": "start_gesture_drawing", "mode": "gesture_control", "color": "blue", "canvas_size": [720, 1280]}
        - {"type": "camera_frame", "image": "base64_data", "timestamp": 123.45}
        - {"type": "stop_drawing"} - Stop drawing session
        - {"type": "close"} - Close WebSocket connection

    - Server → Client:
        - {"type": "opened", "session_id": "ws_gesture_12345", "status": "ready"}
        - {"type": "connection_confirmed", "client_id": "unique_id", "status": "active"}
        - {"type": "drawing_started", "session_id": "gesture_12345", "canvas_size": [720, 1280]}
        - {"type": "gesture_status", "current_gesture": "drawing", "fingers_up": [false, true, false, false, false]}
        - {"type": "canvas_update", "canvas_base64": "data:image/png;base64,...", "stroke_count": 15}
        - {"type": "recognition_result", "recognized_shape": "circle", "confidence": 0.87}
        - {"type": "drawing_stopped", "session_id": "gesture_12345", "final_recognition": {...}}
        - {"type": "closed", "reason": "client_request"}
        - {"type": "error", "message": "MediaPipe initialization failed"}

    Args:
        websocket (WebSocket): The WebSocket connection instance for gesture drawing.

    Note:
        This endpoint processes camera frames and performs gesture recognition
        for interactive drawing. Requires MediaPipe to be properly initialized.
    """
    await websocket.accept()

    # WebSocket session state
    ws_session_id = f"ws_gesture_{int(asyncio.get_event_loop().time() * 1000)}"
    gesture_session_active = False
    session_id = None
    drawing_mode = "gesture_control"
    client_id = None

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "opened",
            "session_id": ws_session_id,
            "status": "ready",
            "message": "WebSocket connection established for gesture drawing"
        })

        while True:
            # Receive client message
            data = await websocket.receive_json()
            message_type = data.get("type", "")

            if message_type == "open":
                # Handle explicit WebSocket open request
                client_id = data.get("client_id", f"client_{int(asyncio.get_event_loop().time() * 1000)}")
                await websocket.send_json({
                    "type": "connection_confirmed",
                    "session_id": ws_session_id,
                    "client_id": client_id,
                    "status": "active"
                })

            elif message_type == "start_gesture_drawing":
                # Start gesture drawing session
                mode = data.get("mode", "gesture_control")
                color = data.get("color", "black")
                canvas_size = data.get("canvas_size", [640, 480])

                # If there's already an active session for this WebSocket, stop it first
                if gesture_session_active:
                    drawing_service.stop_drawing_session()
                    gesture_session_active = False

                # Start drawing session (WebSocket mode - no camera needed)
                result = drawing_service.start_drawing_session(
                    mode=mode,
                    color=color,
                    auto_recognize=True,
                    websocket_mode=True
                )

                if result.get("status") == "error":
                    # If session already exists, try to stop it and restart
                    if "已在進行中" in result.get("message", ""):
                        drawing_service.stop_drawing_session()
                        # Try again after stopping
                        result = drawing_service.start_drawing_session(
                            mode=mode,
                            color=color,
                            auto_recognize=True,
                            websocket_mode=True
                        )

                if result.get("status") == "error":
                    await websocket.send_json({
                        "type": "error",
                        "message": result.get("message", "Failed to start gesture drawing"),
                        "timestamp": data.get("timestamp", 0)
                    })
                else:
                    gesture_session_active = True
                    drawing_mode = mode
                    session_id = f"gesture_{int(data.get('timestamp', 0) * 1000)}"

                    await websocket.send_json({
                        "type": "drawing_started",
                        "session_id": session_id,
                        "canvas_size": canvas_size,
                        "timestamp": data.get("timestamp", 0)
                    })

            elif message_type == "camera_frame" and gesture_session_active:
                # Process camera frame for gesture drawing
                image_data = data.get("image", "")
                timestamp = data.get("timestamp", 0)

                try:
                    # Decode base64 image
                    if image_data.startswith("data:image/"):
                        image_data = image_data.split(",")[1]

                    image_bytes = base64.b64decode(image_data)

                    # Process frame through drawing service
                    result = drawing_service.process_frame_for_gesture_drawing(
                        frame_data=image_bytes,
                        mode=drawing_mode
                    )

                    # Send the processing result back to client
                    await websocket.send_json(result)

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Frame processing error: {str(e)}",
                        "timestamp": timestamp
                    })

            elif message_type == "change_color" and gesture_session_active:
                # Handle color change during drawing
                new_color = data.get("color", "black")
                timestamp = data.get("timestamp", 0)

                try:
                    # Validate color
                    valid_colors = ["black", "red", "green", "blue", "yellow", "purple", "cyan", "white"]
                    if new_color not in valid_colors:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"無效的顏色: {new_color}，支援的顏色: {', '.join(valid_colors)}",
                            "timestamp": timestamp
                        })
                    else:
                        # Change drawing color
                        drawing_service.change_drawing_color(new_color)
                        await websocket.send_json({
                            "type": "color_changed",
                            "color": new_color,
                            "message": f"繪畫顏色已更改為 {new_color}",
                            "timestamp": timestamp
                        })

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"顏色變更錯誤: {str(e)}",
                        "timestamp": timestamp
                    })

            elif message_type == "stop_drawing":
                # Stop gesture drawing session
                if gesture_session_active:
                    result = drawing_service.stop_drawing_session()
                    gesture_session_active = False

                    await websocket.send_json({
                        "type": "drawing_stopped",
                        "session_id": session_id,
                        "final_recognition": result.get("final_recognition", {}),
                        "timestamp": data.get("timestamp", 0)
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No active gesture drawing session",
                        "timestamp": data.get("timestamp", 0)
                    })

            elif message_type == "close":
                # Handle explicit WebSocket close request
                if gesture_session_active:
                    drawing_service.stop_drawing_session()
                    gesture_session_active = False

                await websocket.send_json({
                    "type": "closed",
                    "session_id": ws_session_id,
                    "reason": "client_request",
                    "timestamp": data.get("timestamp", 0)
                })
                break  # Exit the message loop to close the connection

            elif message_type == "ping":
                # Handle heartbeat ping - respond with pong
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp", 0)
                })

            elif message_type == "pong":
                # Handle heartbeat pong - acknowledge silently
                pass

            else:
                # Unknown message type
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unsupported message type: {message_type}",
                    "timestamp": data.get("timestamp", 0)
                })

    except WebSocketDisconnect:
        # Cleanup on disconnect
        if gesture_session_active:
            drawing_service.stop_drawing_session()
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket error: {str(e)}"
            })
        except:
            pass


@router.websocket("/ws/action")
async def websocket_action(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time action detection updates.

    Establishes a persistent WebSocket connection to stream action detection
    results in real-time. Clients receive live updates as human actions are
    detected from camera feeds.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Note:
        Connection automatically handles cleanup on client disconnect.
        Only action-related messages are forwarded to this endpoint.
    """
    await websocket.accept()
    queue = await status_broadcaster.register()
    try:
        while True:
            message = await queue.get()
            if message.get("channel") == "action":
                await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        await status_broadcaster.unregister(queue)


@router.websocket("/ws/emotion")
async def websocket_emotion(websocket: WebSocket) -> None:
    """
    WebSocket 即時情緒分析端點

    接收客戶端發送的影像幀，使用DeepFace進行即時情緒分析，
    並將分析結果即時返回給客戶端。

    支持的訊息格式:
    - 客戶端發送: {"type": "frame", "image": "base64_data", "timestamp": 123.45}
    - 服務器返回: {"type": "result", "emotion_zh": "開心", "confidence": 0.96, ...}

    Args:
        websocket (WebSocket): WebSocket連接實例

    Note:
        WebSocket 本身就是串流協議，不需要額外的 /stream 後綴
    """
    await websocket.accept()

    try:
        while True:
            # 接收客戶端消息
            data = await websocket.receive_json()

            # 處理心跳訊息
            if data.get("type") == "ping":
                await websocket.send_text("pong")
                continue

            if data.get("type") != "frame":
                message_type = data.get("type", "未定義")
                await websocket.send_json({
                    "type": "error",
                    "message": f"不支持的消息類型: {message_type}",
                    "received_data": str(data)[:200]  # 只顯示前200字符以避免過長
                })
                continue

            # 解析base64影像數據
            image_data = data.get("image", "")
            timestamp = data.get("timestamp", 0)

            try:
                # 處理base64影像數據
                if image_data.startswith("data:image/"):
                    # 移除data URL前綴
                    image_data = image_data.split(",")[1]

                # 解碼base64
                image_bytes = base64.b64decode(image_data)

                # 創建臨時檔案
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(image_bytes)
                    temp_path = tmp_file.name

                try:
                    # 使用DeepFace分析情緒
                    result = emotion_service.analyze_image_deepface(temp_path)

                    # 添加時間戳和類型
                    result.update({
                        "type": "result",
                        "timestamp": timestamp,
                        "frame_time": timestamp
                    })

                    # 發送分析結果
                    await websocket.send_json(result)

                finally:
                    # 清理臨時檔案
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"影像分析錯誤: {str(e)}",
                    "timestamp": timestamp
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket錯誤: {str(e)}"
            })
        except:
            pass
