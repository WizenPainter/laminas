import dataclasses
from typing import List, Dict, Tuple, Optional

@dataclasses.dataclass
class StockSheet:
    thickness_mm: int
    width_mm: float
    height_mm: float
    
    def __post_init__(self):
        if any(dim <= 0 for dim in [self.thickness_mm, self.width_mm, self.height_mm]):
            raise ValueError("All dimensions must be positive")

class GlassInventory:
    def __init__(self):
        self.stock_sizes = {
            "CL3": StockSheet(3, 2440, 1830),   # 3mm standard sheet
            "CL4": StockSheet(4, 2440, 1830),   # 4mm standard sheet
            "CL6": StockSheet(6, 3300, 2600),   # 6mm large sheet
            "CL10": StockSheet(10, 3300, 2140), # 10mm large sheet
            "HN6": StockSheet(6, 3300, 2600),   # 6mm large sheet 
            "FIL6": StockSheet(6, 3600, 2600),  # 6mm large sheet 
        }
    
    def get_stock_sheet(self, code: str) -> StockSheet:
        if code not in self.stock_sizes:
            raise ValueError(f"No stock sheet available for code {code}")
        return self.stock_sizes[code]
    
    def add_stock_size(self, code: str, thickness_mm: int, width_mm: float, height_mm: float):
        self.stock_sizes[code] = StockSheet(thickness_mm, width_mm, height_mm)

class Rectangle:
    def __init__(self, width: float, height: float, quantity: int = 1, thickness_mm: int = None):
        self.width = width
        self.height = height
        self.quantity = quantity
        self.thickness_mm = thickness_mm
        self.rotated = False
        self.position = None  # (x, y) tuple

    def can_rotate(self):
        return self.width != self.height

    def get_dimensions(self):
        if self.rotated:
            return self.height, self.width
        return self.width, self.height

class Sheet:
    def __init__(self, stock_sheet: StockSheet):
        self.stock_sheet = stock_sheet
        self.width = stock_sheet.width_mm
        self.height = stock_sheet.height_mm
        self.thickness = stock_sheet.thickness_mm
        self.placed_rectangles = []
        self.spaces = [(0, 0, self.width, self.height)]  # (x, y, width, height)

    def find_best_space(self, rectangle):
        best_space = None
        best_space_index = -1
        min_waste = float('inf')
        should_rotate = False

        for space_index, space in enumerate(self.spaces):
            x, y, space_width, space_height = space

            # Try without rotation
            if rectangle.width <= space_width and rectangle.height <= space_height:
                waste = space_width * space_height - rectangle.width * rectangle.height
                if waste < min_waste:
                    min_waste = waste
                    best_space = space
                    best_space_index = space_index
                    should_rotate = False

            # Try with rotation if possible
            if rectangle.can_rotate() and rectangle.height <= space_width and rectangle.width <= space_height:
                waste = space_width * space_height - rectangle.width * rectangle.height
                if waste < min_waste:
                    min_waste = waste
                    best_space = space
                    best_space_index = space_index
                    should_rotate = True

        return best_space, best_space_index, should_rotate

    def place_rectangle(self, rectangle, space, space_index):
        x, y, space_width, space_height = space
        rect_width, rect_height = rectangle.get_dimensions()
        
        self.spaces.pop(space_index)
        
        if space_width > rect_width:
            self.spaces.append((x + rect_width, y, space_width - rect_width, space_height))
        if space_height > rect_height:
            self.spaces.append((x, y + rect_height, rect_width, space_height - rect_height))
            
        rectangle.position = (x, y)
        self.placed_rectangles.append(rectangle)
        return True

class GlassCuttingOptimizer:
    def __init__(self, inventory: GlassInventory):
        self.inventory = inventory

    def optimize_cutting(self, glass_code: str, pieces: List[Tuple[float, float, int]]) -> List[Sheet]:
        stock_sheet = self.inventory.get_stock_sheet(glass_code)
        
        # Create rectangles from pieces
        rectangles = []
        for width, height, quantity in pieces:
            for _ in range(quantity):
                rectangles.append(Rectangle(width, height, 1, stock_sheet.thickness_mm))
        
        # Sort rectangles by area (largest first)
        rectangles.sort(key=lambda r: r.width * r.height, reverse=True)
        
        sheets = []
        unplaced_rectangles = rectangles.copy()
        
        while unplaced_rectangles:
            current_sheet = Sheet(stock_sheet)
            sheets.append(current_sheet)
            
            placed_any = True
            while placed_any:
                placed_any = False
                i = 0
                while i < len(unplaced_rectangles):
                    rect = unplaced_rectangles[i]
                    best_space, space_index, should_rotate = current_sheet.find_best_space(rect)
                    
                    if best_space is not None:
                        rect.rotated = should_rotate
                        current_sheet.place_rectangle(rect, best_space, space_index)
                        unplaced_rectangles.pop(i)
                        placed_any = True
                    else:
                        i += 1
        
        return sheets

def print_optimization_result(sheets: List[Sheet], glass_code: str):
    print(f"\nOptimization result for {glass_code}:")
    print(f"Total sheets required: {len(sheets)}")
    
    for i, sheet in enumerate(sheets, 1):
        print(f"\nSheet {i} ({sheet.width}x{sheet.height}mm, {sheet.thickness}mm thick):")
        total_area = sheet.width * sheet.height
        used_area = sum(rect.width * rect.height for rect in sheet.placed_rectangles)
        efficiency = (used_area / total_area) * 100
        
        print(f"Sheet efficiency: {efficiency:.1f}%")
        for rect in sheet.placed_rectangles:
            width, height = rect.get_dimensions()
            x, y = rect.position
            rotation_status = "rotated" if rect.rotated else "not rotated"
            print(f"  Piece {width}x{height}mm at position ({x},{y}) - {rotation_status}")

# Example usage
def main():
    # Initialize inventory
    inventory = GlassInventory()
    optimizer = GlassCuttingOptimizer(inventory)
    
    # Example cutting list for CL6 glass
    pieces = [
        (800, 1200, 2),   # 2 pieces of 800x1200mm
        (500, 500, 3),    # 3 pieces of 500x500mm
        (1000, 600, 1),   # 1 piece of 1000x600mm
    ]
    
    glass_code = "CL6"
    print(f"Optimizing cuts for {glass_code} glass:")
    print("Pieces to cut:")
    for width, height, qty in pieces:
        print(f"  {qty}x {width}x{height}mm")
    
    try:
        sheets = optimizer.optimize_cutting(glass_code, pieces)
        print_optimization_result(sheets, glass_code)
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()