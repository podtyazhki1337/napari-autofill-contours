import numpy as np
import napari
from magicgui import magicgui
from skimage import morphology, measure, segmentation, filters
from skimage.util import img_as_ubyte
from scipy import ndimage as ndi


def _lines_from_image_data(img: np.ndarray, force_nonblack: bool, auto_otsu_bias: float):
    """Вернёт bool-маску линий из IMAGE-данных (RGB/RGBA/gray)."""
    A = img
    if A.ndim == 3 and A.shape[-1] in (3, 4):
        A = A[..., :3]
        A8 = img_as_ubyte(A)
        gray = A8.max(axis=-1)  # линии обычно ярче фона
    elif A.ndim == 2:
        A8 = img_as_ubyte(A)
        gray = A8
    else:
        raise ValueError("Unsupported image shape for Image layer")

    if force_nonblack:
        # любой не-чёрный — линия
        lines = gray > 0
    else:
        # авто-порог (Otsu) + небольшой сдвиг (bias) вверх
        try:
            t = filters.threshold_otsu(gray)
        except Exception:
            t = 0
        t = min(255, max(0, int(t + auto_otsu_bias)))
        lines = gray >= t

    return lines.astype(bool)


def _lines_from_labels_data(lab: np.ndarray):
    """Вернёт bool-маску линий из LABELS-данных (контуры инстансов)."""
    if lab.ndim != 2:
        lab = np.squeeze(lab)
    # контуры по меткам (где меняется label)
    edges = segmentation.find_boundaries(lab, mode="outer")
    return edges.astype(bool)


def _autofill_from_labels(labels_data: np.ndarray, dilate_iters: int, min_area: int, bg_neighbors_threshold: int = 5):
    """
    Заполняет области внутри контуров Labels, сохраняя оригинальные ID меток.
    ОГРАНИЧЕНИЕ: Количество заполненных объектов = количество уникальных меток в контурах.
    """
    if labels_data.ndim != 2:
        labels_data = np.squeeze(labels_data)

    unique_labels = np.unique(labels_data)
    unique_labels = unique_labels[unique_labels != 0]

    if len(unique_labels) == 0:
        return labels_data

    print(f"[AutoFillContours] Found {len(unique_labels)} unique contour labels")
    print(f"[AutoFillContours] Max allowed filled objects: {len(unique_labels)}")

    # Создаем результат - сначала копируем исходные контуры
    result = labels_data.copy()

    # Для каждой метки заполняем её внутреннюю область
    for label_id in unique_labels:
        # Маска текущего контура
        contour = (labels_data == label_id)

        # Опционально закрываем разрывы
        if dilate_iters > 0:
            se = morphology.disk(1)
            contour_closed = contour.copy()
            for _ in range(min(2, dilate_iters)):
                contour_closed = morphology.binary_dilation(contour_closed, footprint=se)
        else:
            contour_closed = contour

        # Заполняем ВСЕ дыры внутри этого контура
        filled = ndi.binary_fill_holes(contour_closed)

        # ВАЖНО: Записываем заполненную область с текущей меткой
        # Но НЕ перезаписываем другие уже заполненные метки
        result[filled & (result == 0)] = label_id

    # Теперь определяем фон как области, граничащие со многими метками
    empty_areas = (result == 0)

    # Находим внешний фон
    seed = np.zeros_like(empty_areas, dtype=bool)
    seed[0, :] = empty_areas[0, :]
    seed[-1, :] = empty_areas[-1, :]
    seed[:, 0] = empty_areas[:, 0]
    seed[:, -1] = empty_areas[:, -1]

    outer_bg = morphology.reconstruction(
        seed.astype(np.uint8),
        empty_areas.astype(np.uint8),
        method="dilation"
    ) > 0

    # Внутренние пустоты
    inner_empty = empty_areas & (~outer_bg)

    if np.any(inner_empty):
        # Анализируем внутренние пустоты
        empty_regions = measure.label(inner_empty, connectivity=1, background=0)

        print(f"[AutoFillContours] Analyzing {empty_regions.max()} empty regions...")

        for region_id in range(1, empty_regions.max() + 1):
            region = (empty_regions == region_id)

            # Находим соседние метки
            dilated = morphology.binary_dilation(region, footprint=morphology.disk(2))
            boundary = dilated & (~region) & (result > 0)

            neighboring_labels = np.unique(result[boundary])
            neighboring_labels = neighboring_labels[neighboring_labels != 0]

            num_neighbors = len(neighboring_labels)

            # УЛУЧШЕНИЕ: Разные стратегии в зависимости от количества соседей
            if num_neighbors == 0:
                # Нет соседей - странно, но пропускаем
                continue
            elif num_neighbors == 1:
                # ОДНА МЕТКА - ВСЕГДА заполняем, это явно дырка внутри контура
                result[region] = neighboring_labels[0]
            elif num_neighbors < bg_neighbors_threshold:
                # МАЛО СОСЕДЕЙ - заполняем самой частой меткой
                boundary_labels = result[boundary]
                boundary_labels = boundary_labels[boundary_labels != 0]
                unique, counts = np.unique(boundary_labels, return_counts=True)
                most_common = unique[np.argmax(counts)]

                # Проверяем, доминирует ли одна метка (> 60% границы)
                dominant_ratio = counts.max() / counts.sum()
                if dominant_ratio > 0.6:
                    result[region] = most_common
            else:
                # МНОГО СОСЕДЕЙ - но проверим, может одна метка всё равно доминирует
                boundary_labels = result[boundary]
                boundary_labels = boundary_labels[boundary_labels != 0]
                unique, counts = np.unique(boundary_labels, return_counts=True)

                # Если одна метка составляет > 70% границы - это скорее всего её область
                dominant_ratio = counts.max() / counts.sum()
                if dominant_ratio > 0.7:
                    most_common = unique[np.argmax(counts)]
                    result[region] = most_common
                # Иначе - это действительно фон, оставляем пустым

    # ПРОВЕРКА: Количество уникальных меток в результате не должно превышать исходное
    result_unique = np.unique(result)
    result_unique = result_unique[result_unique != 0]

    if len(result_unique) > len(unique_labels):
        print(f"[AutoFillContours] WARNING: Found {len(result_unique)} filled labels, expected {len(unique_labels)}")
        print(f"[AutoFillContours] Extra labels detected: {set(result_unique) - set(unique_labels)}")
        # Удаляем метки, которых не было в исходных контурах
        for label_id in result_unique:
            if label_id not in unique_labels:
                result[result == label_id] = 0

    # Проверяем, что все исходные метки присутствуют
    final_unique = np.unique(result)
    final_unique = final_unique[final_unique != 0]

    if len(final_unique) < len(unique_labels):
        missing = set(unique_labels) - set(final_unique)
        print(f"[AutoFillContours] WARNING: {len(missing)} labels disappeared after filling: {missing}")

    # Фильтр по площади (только в конце!)
    if min_area > 0:
        removed_count = 0
        for label_id in list(final_unique):  # Копируем список, т.к. будем изменять
            mask = (result == label_id)
            area = np.sum(mask)
            if area < min_area:
                result[mask] = 0
                removed_count += 1
        if removed_count > 0:
            print(f"[AutoFillContours] Removed {removed_count} labels due to min_area filter")

    filled_pixels = np.sum(result > 0)
    contour_pixels = np.sum(labels_data > 0)
    final_label_count = len(np.unique(result)[1:])  # Исключаем 0

    print(f"[AutoFillContours] Contour pixels: {contour_pixels}, Filled pixels: {filled_pixels}")
    print(f"[AutoFillContours] Final label count: {final_label_count}/{len(unique_labels)}")

    return result.astype(np.uint16)


def _autofill_from_lines(lines_bool: np.ndarray, dilate_iters: int, min_area: int):
    """Линии -> авто-заливка всех замкнутых областей -> uint16 Labels."""
    lines = lines_bool.copy()

    # герметизация микро-разрывов
    if dilate_iters > 0:
        se = morphology.square(3)
        for _ in range(int(dilate_iters)):
            lines = morphology.binary_dilation(lines, footprint=se)

    # Инвертируем: True там, где НЕ линии
    inv = ~lines

    # Находим внешний фон через морфологическую реконструкцию от границ
    seed = np.zeros_like(inv, dtype=bool)
    seed[0, :] = inv[0, :]
    seed[-1, :] = inv[-1, :]
    seed[:, 0] = inv[:, 0]
    seed[:, -1] = inv[:, -1]

    outer_background = morphology.reconstruction(
        seed.astype(np.uint8),
        inv.astype(np.uint8),
        method="dilation"
    ) > 0

    # Внутренние области = НЕ линии И НЕ внешний фон
    inside = inv & (~outer_background)

    # Связные компоненты -> ID
    labels = measure.label(inside, connectivity=1, background=0)

    # Фильтр мелочи
    if min_area and min_area > 0 and labels.max() > 0:
        props = measure.regionprops(labels)
        drop = [p.label for p in props if p.area < min_area]
        if drop:
            bad = np.isin(labels, drop)
            labels[bad] = 0
            labels = measure.label(labels > 0, connectivity=1, background=0)

    return labels.astype(np.uint16)


def create_autofill_widget():
    """Фабрика виджета для npe2: возвращает magicgui-виджет."""

    @magicgui(
        call_button="Run Auto-Fill",
        layer={"label": "Source layer (Image/Labels)"},
        force_nonblack={"label": "Force non-black as lines"},
        auto_otsu_bias={"label": "Otsu bias (+)", "min": 0, "max": 40, "step": 1},
        dilate_iters={"label": "Line closing (iters)", "min": 0, "max": 10, "step": 1},
        min_area={"label": "Min area (px)", "min": 0, "max": 50000, "step": 1},
        bg_threshold={"label": "Background threshold (neighbors)", "min": 2, "max": 10, "step": 1},
    )
    def autofill_widget(
            layer: napari.layers.Layer,
            force_nonblack: bool = False,
            auto_otsu_bias: int = 5,
            dilate_iters: int = 2,
            min_area: int = 11,
            bg_threshold: int = 5,
    ):
        """
        Выбери слой с контурами:
          • Image (RGB/RGBA/gray): авто-детект линий (Otsu) или любой не-чёрный.
          • Labels: заполняет области, сохраняя цвета контуров.

        Умный алгоритм:
        - Области с 1 соседом ВСЕГДА заполняются
        - Области с доминирующим соседом (>60-70%) заполняются
        - Количество объектов = количество уникальных меток в контурах
        - Остальное остается фоном
        """
        if layer is None:
            return

        data = layer.data

        # 1) получить маску линий или заполнить метки напрямую
        if isinstance(layer, napari.layers.Labels):
            labels = _autofill_from_labels(
                data,
                dilate_iters=int(dilate_iters),
                min_area=int(min_area),
                bg_neighbors_threshold=int(bg_threshold)
            )
            layer_name = f"{layer.name}_filled"
        elif isinstance(layer, napari.layers.Image):
            try:
                lines = _lines_from_image_data(data, force_nonblack=force_nonblack, auto_otsu_bias=auto_otsu_bias)
                labels = _autofill_from_lines(lines, dilate_iters=int(dilate_iters), min_area=int(min_area))
                layer_name = f"filled_{int(labels.max())}_regions"
            except Exception as e:
                print(f"[AutoFillContours] Image parse failed: {e}")
                return
        else:
            print("[AutoFillContours] Unsupported layer type. Use Image or Labels.")
            return

        # 2) Добавляем результат
        if labels.max() == 0:
            print("[AutoFillContours] No closed regions found!")
        else:
            viewer = napari.current_viewer()
            if isinstance(layer, napari.layers.Labels):
                new_layer = viewer.add_labels(labels, name=layer_name)
                # Копируем colormap
                if hasattr(layer, 'colormap'):
                    new_layer.colormap = layer.colormap
                if hasattr(layer, 'color'):
                    new_layer.color = layer.color
            else:
                viewer.add_labels(labels, name=layer_name)

            print(f"[AutoFillContours] Successfully created filled layer")

    return autofill_widget


# совместимость со старым API
def napari_experimental_provide_dock_widget():
    return [create_autofill_widget]