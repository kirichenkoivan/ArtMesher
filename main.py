import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QPushButton,
    QVBoxLayout, QHBoxLayout, QWidget, QFormLayout, QLineEdit, QListWidget,
    QLabel, QSpinBox, QFileDialog, QColorDialog, QToolBar, QGraphicsLineItem,
    QGraphicsEllipseItem
)
from PyQt5.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt5.QtGui import QPen, QColor, QBrush, QCursor


class Vertex:
    """Описание вершины"""

    def __init__(self, position, color, tex_coords, tex_id):
        self.position = position  # (x, y)
        self.color = color  # QColor
        self.tex_coords = tex_coords  # (u, v)
        self.tex_id = tex_id  # int


class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, editor):
        super().__init__(scene)
        self.editor = editor

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.editor.handle_mouse_click(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.editor.selected_vertex and self.editor.selected_arrow:
            self.editor.move_vertex(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.editor.selected_arrow = None
        super().mouseReleaseEvent(event)


class Arrow(QGraphicsLineItem):
    def __init__(self, start, end, direction, editor):
        super().__init__(start.x(), start.y(), end.x(), end.y())
        self.direction = direction
        self.editor = editor
        self.setPen(QPen(Qt.red, 2))
        self.setCursor(QCursor(Qt.SizeAllCursor))

    def mousePressEvent(self, event):
        self.editor.selected_arrow = self
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.editor.selected_arrow == self:
            self.editor.move_vertex(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.editor.selected_arrow = None
        super().mouseReleaseEvent(event)


class Editor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2D Shape Editor")
        self.setGeometry(100, 100, 1000, 600)

        # Панель инструментов
        self.toolbar = QToolBar("Tools")
        self.addToolBar(self.toolbar)

        self.fill_tool = QPushButton("Fill")
        self.fill_tool.clicked.connect(self.fill_shape)
        self.toolbar.addWidget(self.fill_tool)

        # Основной layout
        self.main_layout = QHBoxLayout()
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.central_widget)

        # Графическая сцена и вид
        self.scene = QGraphicsScene()
        self.view = CustomGraphicsView(self.scene, self)
        self.main_layout.addWidget(self.view)

        # Список вершин и связей
        self.vertices = []  # Список вершин
        self.edges = []  # Список ребер (связей)
        self.closed = False  # Флаг завершенности фигуры

        # Панель редактирования точки
        self.properties_panel = self.create_properties_panel()
        self.main_layout.addWidget(self.properties_panel)

        # Кнопки управления
        controls_layout = QVBoxLayout()
        self.close_shape_button = QPushButton("Close Shape")
        self.close_shape_button.clicked.connect(self.close_shape)
        controls_layout.addWidget(self.close_shape_button)

        self.export_button = QPushButton("Export to JSON")
        self.export_button.clicked.connect(self.export_to_json)
        controls_layout.addWidget(self.export_button)

        self.main_layout.addLayout(controls_layout)

        # Инструменты
        self.current_color = QColor(255, 255, 255)
        self.selected_vertex = None
        self.selected_arrow = None

        # Привязка событий
        self.view.setMouseTracking(True)

    def create_properties_panel(self):
        """Создает панель свойств"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Список точек
        self.points_list = QListWidget()
        self.points_list.currentRowChanged.connect(self.select_vertex_from_list)
        layout.addWidget(self.points_list)

        # Заголовок
        layout.addWidget(QLabel("Point Properties"))

        # Форма редактирования
        self.form_layout = QFormLayout()

        self.x_edit = QLineEdit()
        self.x_edit.setReadOnly(True)
        self.form_layout.addRow("X:", self.x_edit)

        self.y_edit = QLineEdit()
        self.y_edit.setReadOnly(True)
        self.form_layout.addRow("Y:", self.y_edit)

        self.r_edit = QSpinBox()
        self.r_edit.setRange(0, 255)
        self.r_edit.valueChanged.connect(self.update_color_from_rgb)
        self.form_layout.addRow("R:", self.r_edit)

        self.g_edit = QSpinBox()
        self.g_edit.setRange(0, 255)
        self.g_edit.valueChanged.connect(self.update_color_from_rgb)
        self.form_layout.addRow("G:", self.g_edit)

        self.b_edit = QSpinBox()
        self.b_edit.setRange(0, 255)
        self.b_edit.valueChanged.connect(self.update_color_from_rgb)
        self.form_layout.addRow("B:", self.b_edit)

        self.color_display = QLabel()
        self.color_display.setFixedSize(50, 20)
        self.color_display.setStyleSheet("background-color: white; border: 1px solid black;")
        self.form_layout.addRow("Color:", self.color_display)

        self.tex_coords_edit = QLineEdit("0.0, 0.0")
        self.form_layout.addRow("Tex Coords:", self.tex_coords_edit)

        self.tex_id_edit = QSpinBox()
        self.tex_id_edit.setMinimum(0)
        self.form_layout.addRow("Tex ID:", self.tex_id_edit)

        color_button = QPushButton("Select Color")
        color_button.clicked.connect(self.select_color)
        self.form_layout.addRow(color_button)

        layout.addLayout(self.form_layout)

        return panel

    def handle_mouse_click(self, event):
        """Обрабатывает клики мыши на сцене"""
        if self.closed:
            return  # В завершенной фигуре нельзя добавлять точки

        position = self.view.mapToScene(event.pos())
        # Коррекция координат в пределах от -1 до 1
        norm_position = QPointF(
            self.normalize_position(position.x(), -1, 1),
            self.normalize_position(position.y(), -1, 1)
        )

        vertex = Vertex(
            position=(norm_position.x(), norm_position.y()),
            color=self.current_color,
            tex_coords=(0.0, 0.0),
            tex_id=0
        )
        self.vertices.append(vertex)

        # Рисуем точку
        ellipse = self.scene.addEllipse(norm_position.x() - 5, norm_position.y() - 5, 10, 10, QPen(Qt.black),
                                        QBrush(self.current_color))
        ellipse.setFlag(ellipse.ItemIsSelectable)
        ellipse.setData(0, len(self.vertices) - 1)

        # Обновляем список точек
        self.points_list.addItem(f"Point {len(self.vertices) - 1}: ({norm_position.x()}, {norm_position.y()})")

        # Соединяем с предыдущей точкой
        if len(self.vertices) > 1:
            prev = self.vertices[-2]
            self.edges.append((prev, vertex))
            self.scene.addLine(prev.position[0], prev.position[1], norm_position.x(), norm_position.y(), QPen(Qt.black))

    def normalize_position(self, pos, min_val, max_val):
        """Нормализует координаты в пределах от -1 до 1"""
        return 2 * (pos - min_val) / (max_val - min_val) - 1

    def select_vertex_from_list(self, index):
        """Выбирает точку из списка"""
        if index < 0 or index >= len(self.vertices):
            return

        self.selected_vertex = self.vertices[index]
        self.x_edit.setText(str(self.selected_vertex.position[0]))
        self.y_edit.setText(str(self.selected_vertex.position[1]))
        self.r_edit.setValue(self.selected_vertex.color.red())
        self.g_edit.setValue(self.selected_vertex.color.green())
        self.b_edit.setValue(self.selected_vertex.color.blue())
        self.color_display.setStyleSheet(
            f"background-color: {self.selected_vertex.color.name()}; border: 1px solid black;")

        # Удаляем старые стрелки
        self.remove_arrows()

        # Добавляем новые стрелки
        self.add_arrows()

    def update_color_from_rgb(self):
        """Обновляет цвет точки из RGB"""
        if not self.selected_vertex:
            return
        new_color = QColor(self.r_edit.value(), self.g_edit.value(), self.b_edit.value())
        self.selected_vertex.color = new_color
        self.color_display.setStyleSheet(f"background-color: {new_color.name()}; border: 1px solid black;")

    def select_color(self):
        color = QColorDialog.getColor(self.current_color, self)
        if color.isValid():
            self.current_color = color
            self.r_edit.setValue(color.red())
            self.g_edit.setValue(color.green())
            self.b_edit.setValue(color.blue())
            self.color_display.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")

    def fill_shape(self):
        """Заливка фигуры текущим цветом"""
        if not self.vertices:
            return

        for vertex in self.vertices:
            vertex.color = self.current_color

        # Обновляем цвета на сцене
        for item in self.scene.items():
            if isinstance(item, QGraphicsEllipseItem):
                index = item.data(0)
                if index is not None and 0 <= index < len(self.vertices):
                    vertex = self.vertices[index]
                    item.setBrush(QBrush(vertex.color))

        # Обновляем список точек
        self.update_points_list()

    def update_points_list(self):
        """Обновляет список точек"""
        self.points_list.clear()
        for i, vertex in enumerate(self.vertices):
            self.points_list.addItem(f"Point {i}: ({vertex.position[0]}, {vertex.position[1]})")

    def close_shape(self):
        """Замыкает фигуру"""
        if len(self.vertices) < 3 or self.closed:
            return
        first, last = self.vertices[0], self.vertices[-1]
        self.edges.append((last, first))
        self.scene.addLine(last.position[0], last.position[1], first.position[0], first.position[1], QPen(Qt.black))
        self.closed = True

    def export_to_json(self):
        """Экспортирует данные в JSON"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save JSON", "", "JSON Files (*.json)")
        if not file_path:
            return

        vertices_data = []
        for vertex in self.vertices:
            vertices_data.append({
                "position": [vertex.position[0], vertex.position[1]],
                "color": [vertex.color.red(), vertex.color.green(), vertex.color.blue()],
                "texCoords": vertex.tex_coords,
                "texID": vertex.tex_id
            })

        indices = self.triangulate()

        with open(file_path, "w") as file:
            json.dump({
                "vertices": vertices_data,
                "indices": indices
            }, file, indent=4)
        print(f"Exported to {file_path}")

    def triangulate(self):
        """Простой метод для триангуляции (для примера)"""
        indices = []
        for i in range(1, len(self.vertices) - 1):
            indices.extend([0, i, i + 1])
        return indices

    def add_arrows(self):
        """Добавляет стрелки для перемещения точки"""
        if not self.selected_vertex:
            return

        pos = QPointF(*self.selected_vertex.position)
        arrow_length = 20

        # Стрелка по оси X
        self.arrow_x = Arrow(pos, pos + QPointF(arrow_length, 0), 'x', self)
        self.scene.addItem(self.arrow_x)

        # Стрелка по оси Y
        self.arrow_y = Arrow(pos, pos + QPointF(0, arrow_length), 'y', self)
        self.scene.addItem(self.arrow_y)

    def remove_arrows(self):
        """Удаляет стрелки"""
        if hasattr(self, 'arrow_x'):
            self.scene.removeItem(self.arrow_x)
        if hasattr(self, 'arrow_y'):
            self.scene.removeItem(self.arrow_y)

    def move_vertex(self, event):
        """Перемещает выбранную точку"""
        if not self.selected_vertex or not self.selected_arrow:
            return

        pos = self.view.mapToScene(event.pos())
        norm_pos = QPointF(
            self.normalize_position(pos.x(), -1, 1),
            self.normalize_position(pos.y(), -1, 1)
        )

        if self.selected_arrow.direction == 'x':
            self.selected_vertex.position = (norm_pos.x(), self.selected_vertex.position[1])
        elif self.selected_arrow.direction == 'y':
            self.selected_vertex.position = (self.selected_vertex.position[0], norm_pos.y())

        # Обновляем позицию точки на сцене
        self.update_vertex_position()

    def update_vertex_position(self):
        """Обновляет позицию точки на сцене"""
        if not self.selected_vertex:
            return

        pos = QPointF(*self.selected_vertex.position)

        # Обновляем позицию точки
        for item in self.scene.items():
            if isinstance(item, QGraphicsEllipseItem) and item.data(0) == self.vertices.index(self.selected_vertex):
                item.setRect(pos.x() - 5, pos.y() - 5, 10, 10)

        # Обновляем позиции стрелок
        self.arrow_x.setLine(pos.x(), pos.y(), pos.x() + 20, pos.y())
        self.arrow_y.setLine(pos.x(), pos.y(), pos.x(), pos.y() + 20)

        # Обновляем линии, соединяющие точки
        self.update_edges()

        # Обновляем список точек
        self.update_points_list()

    def update_edges(self):
        """Обновляет линии, соединяющие точки"""
        for edge in self.edges:
            start, end = edge
            start_pos = QPointF(*start.position)
            end_pos = QPointF(*end.position)
            for item in self.scene.items():
                if isinstance(item, QGraphicsLineItem):
                    if (item.line().p1() == start_pos and item.line().p2() == end_pos) or (
                            item.line().p1() == end_pos and item.line().p2() == start_pos):
                        item.setLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = Editor()
    editor.show()
    sys.exit(app.exec_())