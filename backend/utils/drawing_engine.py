# =============================================================================
# drawing_engine.py - 繪畫引擎核心模組
# =============================================================================
# 處理手勢繪畫的核心引擎，包含畫布管理、筆刷控制、顏色系統等功能
# =============================================================================

import cv2
import numpy as np
import base64
import json
import math
from typing import Tuple, Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
from io import BytesIO
from PIL import Image
import time


class BrushType(Enum):
    """筆刷類型枚舉"""
    NORMAL = "normal"
    SMOOTH = "smooth"
    ERASER = "eraser"


@dataclass
class StrokePoint:
    """筆觸點數據結構"""
    x: int
    y: int
    pressure: float = 1.0
    timestamp: float = 0.0


@dataclass
class Stroke:
    """筆觸數據結構"""
    points: List[StrokePoint]
    color: Tuple[int, int, int]
    size: int
    brush_type: BrushType
    opacity: float = 1.0


@dataclass
class CanvasState:
    """畫布狀態數據結構"""
    width: int
    height: int
    background_color: Tuple[int, int, int]
    total_strokes: int
    current_color: Tuple[int, int, int]
    current_size: int
    current_brush: BrushType


class DrawingEngine:
    """繪畫引擎核心類"""

    # 預設配置
    DEFAULT_CANVAS_SIZE = (720, 1280, 3)  # (height, width, channels)
    DEFAULT_BACKGROUND_COLOR = (255, 255, 255)  # 白色背景
    DEFAULT_BRUSH_COLOR = (0, 0, 255)  # 紅色筆刷
    DEFAULT_BRUSH_SIZE = 15

    # 顏色預設 (BGR格式)
    COLORS = {
        'red': (0, 0, 255),
        'blue': (255, 0, 0),
        'green': (0, 255, 0),
        'yellow': (0, 255, 255),
        'purple': (255, 0, 255),
        'orange': (0, 165, 255),
        'black': (0, 0, 0),
        'white': (255, 255, 255),
        'pink': (203, 192, 255),
        'brown': (42, 42, 165)
    }

    # 筆刷大小範圍
    MIN_BRUSH_SIZE = 1
    MAX_BRUSH_SIZE = 50

    def __init__(self, canvas_size: Tuple[int, int] = None,
                 background_color: Tuple[int, int, int] = None):
        """
        初始化繪畫引擎

        Args:
            canvas_size: 畫布大小 (width, height)
            background_color: 背景顏色 (B, G, R)
        """
        # 設定畫布大小
        if canvas_size:
            self.canvas_height, self.canvas_width = canvas_size[1], canvas_size[0]
        else:
            self.canvas_height, self.canvas_width = self.DEFAULT_CANVAS_SIZE[:2]

        # 設定背景顏色
        self.background_color = background_color or self.DEFAULT_BACKGROUND_COLOR

        # 初始化畫布
        self.canvas = np.full(
            (self.canvas_height, self.canvas_width, 3),
            self.background_color,
            dtype=np.uint8
        )

        # 繪畫狀態
        self.current_color = self.DEFAULT_BRUSH_COLOR
        self.current_size = self.DEFAULT_BRUSH_SIZE
        self.current_brush = BrushType.NORMAL
        self.current_opacity = 1.0

        # 筆觸歷史
        self.strokes = []
        self.current_stroke = None
        self.total_points = 0

        # 性能優化
        self.dirty_regions = []  # 需要更新的區域
        self.last_position = None
        self.drawing_active = False

        # 平滑處理
        self.smoothing_enabled = True
        self.smoothing_factor = 0.3
        self.min_distance_threshold = 5  # 最小移動距離

        # 統計資訊
        self.creation_time = time.time()
        self.last_modified = time.time()

    def start_stroke(self, x: int, y: int, pressure: float = 1.0) -> bool:
        """
        開始新的筆觸

        Args:
            x: X座標
            y: Y座標
            pressure: 壓力值 (0.0-1.0)

        Returns:
            bool: 是否成功開始筆觸
        """
        if not self._is_valid_coordinate(x, y):
            return False

        # 創建新筆觸
        self.current_stroke = Stroke(
            points=[StrokePoint(x, y, pressure, time.time())],
            color=self.current_color,
            size=self.current_size,
            brush_type=self.current_brush,
            opacity=self.current_opacity
        )

        self.last_position = (x, y)
        self.drawing_active = True

        # 在畫布上繪製起始點
        self._draw_point(x, y, self.current_size)

        return True

    def add_stroke_point(self, x: int, y: int, pressure: float = 1.0) -> bool:
        """
        添加筆觸點並繪製線段

        Args:
            x: X座標
            y: Y座標
            pressure: 壓力值

        Returns:
            bool: 是否成功添加點
        """
        if not self.drawing_active or not self.current_stroke:
            return False

        if not self._is_valid_coordinate(x, y):
            return False

        # 檢查是否移動距離足夠
        if self.last_position:
            distance = self._calculate_distance(self.last_position, (x, y))
            if distance < self.min_distance_threshold:
                return False

        # 添加點到當前筆觸
        stroke_point = StrokePoint(x, y, pressure, time.time())
        self.current_stroke.points.append(stroke_point)

        # 繪製線段
        if self.last_position:
            self._draw_line(self.last_position, (x, y), pressure)

        self.last_position = (x, y)
        self.total_points += 1
        self.last_modified = time.time()

        return True

    def end_stroke(self) -> bool:
        """
        結束當前筆觸

        Returns:
            bool: 是否成功結束筆觸
        """
        if not self.drawing_active or not self.current_stroke:
            return False

        # 將當前筆觸添加到歷史
        if len(self.current_stroke.points) > 1:  # 至少需要2個點
            self.strokes.append(self.current_stroke)

        # 重置狀態
        self.current_stroke = None
        self.last_position = None
        self.drawing_active = False

        return True

    def _draw_point(self, x: int, y: int, size: int):
        """繪製單個點"""
        if self.current_brush == BrushType.ERASER:
            cv2.circle(self.canvas, (x, y), size, self.background_color, -1)
        else:
            cv2.circle(self.canvas, (x, y), size, self.current_color, -1)

    def _draw_line(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int], pressure: float = 1.0):
        """
        繪製線段

        Args:
            start_pos: 起始位置
            end_pos: 結束位置
            pressure: 壓力值
        """
        if self.smoothing_enabled:
            self._draw_smooth_line(start_pos, end_pos, pressure)
        else:
            self._draw_direct_line(start_pos, end_pos, pressure)

    def _draw_direct_line(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int], pressure: float):
        """直接繪製線段"""
        size = max(1, int(self.current_size * pressure))

        if self.current_brush == BrushType.ERASER:
            cv2.line(self.canvas, start_pos, end_pos, self.background_color, size)
        else:
            cv2.line(self.canvas, start_pos, end_pos, self.current_color, size)

    def _draw_smooth_line(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int], pressure: float):
        """繪製平滑線段"""
        x1, y1 = start_pos
        x2, y2 = end_pos

        # 計算中間點進行平滑處理
        distance = self._calculate_distance(start_pos, end_pos)
        steps = max(1, int(distance / 2))

        size = max(1, int(self.current_size * pressure))
        color = self.background_color if self.current_brush == BrushType.ERASER else self.current_color

        for i in range(steps + 1):
            t = i / max(1, steps)
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)

            cv2.circle(self.canvas, (x, y), size, color, -1)

    def change_brush_color(self, color: str) -> bool:
        """
        改變筆刷顏色

        Args:
            color: 顏色名稱或十六進制值

        Returns:
            bool: 操作是否成功
        """
        if color.lower() in self.COLORS:
            self.current_color = self.COLORS[color.lower()]
            return True
        elif color.startswith('#') and len(color) == 7:
            # 解析十六進制顏色
            try:
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                self.current_color = (b, g, r)  # OpenCV使用BGR
                return True
            except ValueError:
                return False
        else:
            return False

    def set_brush_size(self, size: int) -> bool:
        """
        設置筆刷大小

        Args:
            size: 筆刷大小

        Returns:
            bool: 設置是否成功
        """
        if self.MIN_BRUSH_SIZE <= size <= self.MAX_BRUSH_SIZE:
            self.current_size = size
            return True
        return False

    def set_brush_type(self, brush_type: str) -> bool:
        """
        設置筆刷類型

        Args:
            brush_type: 筆刷類型字符串

        Returns:
            bool: 設置是否成功
        """
        try:
            self.current_brush = BrushType(brush_type.lower())
            return True
        except ValueError:
            return False

    def clear_canvas(self) -> bool:
        """
        清空畫布

        Returns:
            bool: 操作是否成功
        """
        try:
            # 重置畫布
            self.canvas = np.full(
                (self.canvas_height, self.canvas_width, 3),
                self.background_color,
                dtype=np.uint8
            )

            # 清空筆觸歷史
            self.strokes = []
            self.current_stroke = None
            self.total_points = 0

            # 重置狀態
            self.last_position = None
            self.drawing_active = False
            self.last_modified = time.time()

            return True
        except Exception:
            return False

    def get_canvas_image(self, format: str = "base64") -> str:
        """
        獲取畫布圖像

        Args:
            format: 輸出格式 "base64" | "numpy" | "bytes"

        Returns:
            str: 畫布數據
        """
        try:
            if format == "numpy":
                return self.canvas.copy()

            elif format == "base64":
                # 轉換為RGB格式
                rgb_canvas = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2RGB)

                # 轉換為PIL Image
                pil_image = Image.fromarray(rgb_canvas)

                # 轉換為base64
                buffer = BytesIO()
                pil_image.save(buffer, format='PNG')
                img_bytes = buffer.getvalue()
                buffer.close()

                base64_string = base64.b64encode(img_bytes).decode('utf-8')
                return f"data:image/png;base64,{base64_string}"

            elif format == "bytes":
                # 編碼為PNG bytes
                _, buffer = cv2.imencode('.png', self.canvas)
                return buffer.tobytes()

            else:
                raise ValueError(f"不支援的格式: {format}")

        except Exception as e:
            print(f"獲取畫布圖像錯誤: {e}")
            return ""

    def save_canvas(self, filepath: str) -> bool:
        """
        保存畫布到檔案

        Args:
            filepath: 保存路徑

        Returns:
            bool: 保存是否成功
        """
        try:
            # 轉換為RGB並保存
            rgb_canvas = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_canvas)
            pil_image.save(filepath)
            return True
        except Exception as e:
            print(f"保存畫布錯誤: {e}")
            return False

    def get_canvas_state(self) -> Dict[str, Any]:
        """
        獲取畫布狀態資訊

        Returns:
            Dict: 畫布狀態
        """
        return {
            'width': self.canvas_width,
            'height': self.canvas_height,
            'background_color': self.background_color,
            'total_strokes': len(self.strokes),
            'total_points': self.total_points,
            'current_color': self.current_color,
            'current_size': self.current_size,
            'current_brush': self.current_brush.value,
            'current_opacity': self.current_opacity,
            'drawing_active': self.drawing_active,
            'creation_time': self.creation_time,
            'last_modified': self.last_modified,
            'available_colors': list(self.COLORS.keys()),
            'brush_size_range': [self.MIN_BRUSH_SIZE, self.MAX_BRUSH_SIZE]
        }

    def get_stroke_history(self) -> List[Dict[str, Any]]:
        """
        獲取筆觸歷史

        Returns:
            List[Dict]: 筆觸歷史數據
        """
        history = []
        for stroke in self.strokes:
            stroke_data = {
                'color': stroke.color,
                'size': stroke.size,
                'brush_type': stroke.brush_type.value,
                'opacity': stroke.opacity,
                'point_count': len(stroke.points),
                'start_time': stroke.points[0].timestamp if stroke.points else 0,
                'end_time': stroke.points[-1].timestamp if stroke.points else 0
            }
            history.append(stroke_data)
        return history

    def undo_last_stroke(self) -> bool:
        """
        撤銷上一筆觸

        Returns:
            bool: 撤銷是否成功
        """
        if not self.strokes:
            return False

        try:
            # 移除最後一個筆觸
            self.strokes.pop()

            # 重繪整個畫布
            self._redraw_canvas()

            self.last_modified = time.time()
            return True
        except Exception:
            return False

    def _redraw_canvas(self):
        """重繪整個畫布"""
        # 清空畫布
        self.canvas = np.full(
            (self.canvas_height, self.canvas_width, 3),
            self.background_color,
            dtype=np.uint8
        )

        # 重繪所有筆觸
        for stroke in self.strokes:
            # 暫時設置筆刷屬性
            old_color = self.current_color
            old_size = self.current_size
            old_brush = self.current_brush

            self.current_color = stroke.color
            self.current_size = stroke.size
            self.current_brush = stroke.brush_type

            # 繪製筆觸的所有點
            for i, point in enumerate(stroke.points):
                if i == 0:
                    self._draw_point(point.x, point.y, stroke.size)
                else:
                    prev_point = stroke.points[i-1]
                    self._draw_line(
                        (prev_point.x, prev_point.y),
                        (point.x, point.y),
                        point.pressure
                    )

            # 恢復筆刷屬性
            self.current_color = old_color
            self.current_size = old_size
            self.current_brush = old_brush

    def resize_canvas(self, new_width: int, new_height: int) -> bool:
        """
        調整畫布大小

        Args:
            new_width: 新寬度
            new_height: 新高度

        Returns:
            bool: 調整是否成功
        """
        try:
            # 創建新畫布
            new_canvas = np.full(
                (new_height, new_width, 3),
                self.background_color,
                dtype=np.uint8
            )

            # 計算縮放比例
            scale_x = new_width / self.canvas_width
            scale_y = new_height / self.canvas_height

            # 縮放現有內容
            resized_content = cv2.resize(
                self.canvas,
                (new_width, new_height),
                interpolation=cv2.INTER_AREA
            )

            # 更新畫布
            self.canvas = resized_content
            self.canvas_width = new_width
            self.canvas_height = new_height

            # 更新筆觸座標
            for stroke in self.strokes:
                for point in stroke.points:
                    point.x = int(point.x * scale_x)
                    point.y = int(point.y * scale_y)

            self.last_modified = time.time()
            return True

        except Exception as e:
            print(f"調整畫布大小錯誤: {e}")
            return False

    def _is_valid_coordinate(self, x: int, y: int) -> bool:
        """檢查座標是否有效"""
        return 0 <= x < self.canvas_width and 0 <= y < self.canvas_height

    def _calculate_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """計算兩點間距離"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def get_canvas_statistics(self) -> Dict[str, Any]:
        """
        獲取畫布統計資訊

        Returns:
            Dict: 統計資訊
        """
        total_stroke_length = 0
        color_usage = {}

        for stroke in self.strokes:
            # 計算筆觸長度
            stroke_length = 0
            for i in range(1, len(stroke.points)):
                prev_point = stroke.points[i-1]
                curr_point = stroke.points[i]
                stroke_length += self._calculate_distance(
                    (prev_point.x, prev_point.y),
                    (curr_point.x, curr_point.y)
                )
            total_stroke_length += stroke_length

            # 統計顏色使用
            color_key = f"{stroke.color[0]},{stroke.color[1]},{stroke.color[2]}"
            color_usage[color_key] = color_usage.get(color_key, 0) + 1

        return {
            'total_strokes': len(self.strokes),
            'total_points': self.total_points,
            'total_stroke_length': total_stroke_length,
            'average_stroke_length': total_stroke_length / max(1, len(self.strokes)),
            'color_usage': color_usage,
            'canvas_coverage': self._calculate_canvas_coverage(),
            'session_duration': time.time() - self.creation_time
        }

    def _calculate_canvas_coverage(self) -> float:
        """計算畫布覆蓋率"""
        if not self.strokes:
            return 0.0

        # 簡單的覆蓋率計算：非背景色像素比例
        non_background_pixels = 0
        total_pixels = self.canvas_width * self.canvas_height

        for y in range(0, self.canvas_height, 10):  # 取樣檢查以提高效率
            for x in range(0, self.canvas_width, 10):
                pixel = self.canvas[y, x]
                if not np.array_equal(pixel, self.background_color):
                    non_background_pixels += 100  # 每個取樣點代表100像素

        coverage = min(1.0, non_background_pixels / total_pixels)
        return coverage

    def cleanup(self):
        """清理資源"""
        self.canvas = None
        self.strokes = []
        self.current_stroke = None