# ⚠️ 需要重啟 Docker 容器

## 修改內容

剛剛對 `backend/services/rps_game_service.py` 做了重大修改：

1. ✅ 移除回合循環 - 永遠只玩一次
2. ✅ 移除分數累積系統
3. ✅ 移除所有 `time.sleep()` 延遲
4. ✅ 簡化為單次對決模式

## 重啟步驟

```bash
# 方法 1: 重啟容器
docker-compose restart

# 方法 2: 完整重建（如果 restart 無效）
docker-compose down
docker-compose up -d

# 方法 3: 只重啟後端服務
docker-compose restart backend
```

## 驗證

重啟後，測試遊戲應該：
- ✅ 只玩一回合
- ✅ 不會出現「第 2 回合」
- ✅ 平手也會結束
- ✅ 結果顯示後立即進入 `game_finished` 階段

## 修改摘要

### 後端 (`rps_game_service.py`)

**遊戲循環**：
```python
# 顯示結果
self._show_result()

# 🎯 永遠只玩一回合，不管結果直接結束
logger.info("單次對決結束")
self._finish_game()
break
```

**結束遊戲**：
```python
def _finish_game(self):
    """結束遊戲（單次對決模式）"""
    self.game_state = GameState.FINISHED

    # 根據本回合結果決定訊息
    message = result_messages.get(self.current_result, "對決結束")

    self._broadcast({
        "stage": "game_finished",
        "message": f"遊戲結束！{message}",
        ...
    })

    # 不要 sleep，直接設為 IDLE
    self.game_state = GameState.IDLE
```

### 前端 (`index.html`)

**UI 修改**：
```html
<!-- 修改前 -->
<span>分數: 你 0 - 0 AI</span>

<!-- 修改後 -->
<span>模式: 單次對決</span>
<span>手勢辨識: MediaPipe</span>
```
