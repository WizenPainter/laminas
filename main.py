import json
import dataclasses
import pandas as pd
from typing import List, Dict, Tuple, Optional

from utils import process_dataframe
from produccion import reduce_to_same_glass, get_produccion

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
            "CL10": StockSheet(10, 3600, 2600), # 10mm large sheet
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


def transform_glass_data(glass_data: dict) -> dict:
    """
    Transform the JSON glass data into a format suitable for the optimizer.
    Returns a dictionary with glass codes as keys and lists of (width, height, quantity) tuples as values.
    
    Args:
        glass_data (dict): The input JSON data structure with glass specifications
        
    Returns:
        dict: Dictionary with glass codes mapping to lists of (width, height, quantity) tuples
    """
    transformed_data = {}
    
    for glass_code, glass_info in glass_data.items():
        pieces = []
        for item in glass_info['data']:
            # Parse the dimensions from the "Measures" field
            dimensions = item['Measures'].split('x')
            if len(dimensions) != 2:
                print(f"Warning: Skipping invalid measure format: {item['Measures']}")
                continue
                
            try:
                width = float(dimensions[0])
                height = float(dimensions[1])
                quantity = int(item['Pzs.'])
                
                # Add the piece to the list
                pieces.append((width, height, quantity))
            except (ValueError, IndexError) as e:
                print(f"Warning: Error processing {item['Measures']}: {e}")
                continue
        
        transformed_data[glass_code] = pieces
    
    return transformed_data


def optimize_all_glass(data: dict, optimizer: GlassCuttingOptimizer, output_json: bool = False):
    """
    Run optimization for all glass types in the data.
    
    Args:
        data (dict): The transformed glass data
        optimizer (GlassCuttingOptimizer): Instance of the glass cutting optimizer
        output_json (bool): If True, return results in JSON format
        
    Returns:
        dict: Either the raw optimization results or JSON-formatted results
    """
    results = {}
    json_results = {}
    
    for glass_code, pieces in data.items():
        print(f"\nProcessing {glass_code}:")
        print(f"Total number of different sizes: {len(pieces)}")
        total_pieces = sum(qty for _, _, qty in pieces)
        print(f"Total number of pieces: {total_pieces}")
        
        try:
            sheets = optimizer.optimize_cutting(glass_code, pieces)
            if not output_json:
                print_optimization_result(sheets, glass_code)
            results[glass_code] = sheets
            
            # Convert to JSON-serializable format immediately for each glass type
            if output_json:
                total_area = sum(sheet.width * sheet.height for sheet in sheets)
                used_area = sum(
                    sum(rect.width * rect.height for rect in sheet.placed_rectangles)
                    for sheet in sheets
                )
                overall_efficiency = (used_area / total_area * 100) if total_area > 0 else 0
                
                json_results[glass_code] = {
                    "summary": {
                        "total_sheets": len(sheets),
                        "total_pieces": sum(len(sheet.placed_rectangles) for sheet in sheets),
                        "overall_efficiency": round(overall_efficiency, 2),
                        "total_area": total_area,
                        "used_area": used_area
                    },
                    "sheets": []
                }
                
                # Convert each sheet to a dictionary
                for sheet in sheets:
                    sheet_dict = {
                        "dimensions": {
                            "width": sheet.width,
                            "height": sheet.height,
                            "thickness": sheet.thickness
                        },
                        "pieces": []
                    }
                    
                    # Calculate sheet efficiency
                    sheet_area = sheet.width * sheet.height
                    used_sheet_area = sum(rect.width * rect.height for rect in sheet.placed_rectangles)
                    sheet_dict["efficiency"] = round((used_sheet_area / sheet_area * 100), 2)
                    sheet_dict["total_area"] = sheet_area
                    sheet_dict["used_area"] = used_sheet_area
                    
                    # Convert each piece to a dictionary
                    for rect in sheet.placed_rectangles:
                        piece_dict = {
                            "width": rect.width,
                            "height": rect.height,
                            "position": {
                                "x": rect.position[0],
                                "y": rect.position[1]
                            },
                            "rotated": rect.rotated,
                            "dimensions_after_rotation": {
                                "width": rect.height if rect.rotated else rect.width,
                                "height": rect.width if rect.rotated else rect.height
                            }
                        }
                        sheet_dict["pieces"].append(piece_dict)
                    
                    json_results[glass_code]["sheets"].append(sheet_dict)
                
        except ValueError as e:
            print(f"Error processing {glass_code}: {e}")
    
    return json_results if output_json else results



def convert_sheet_to_dict(sheet: Sheet) -> dict:
    """
    Convert a Sheet object to a dictionary representation.
    """
    total_area = sheet.width * sheet.height
    used_area = sum(rect.width * rect.height for rect in sheet.placed_rectangles)
    efficiency = (used_area / total_area) * 100
    
    return {
        "dimensions": {
            "width": sheet.width,
            "height": sheet.height,
            "thickness": sheet.thickness
        },
        "efficiency": round(efficiency, 2),
        "total_area": total_area,
        "used_area": used_area,
        "pieces": [
            {
                "width": rect.width,
                "height": rect.height,
                "position": {
                    "x": rect.position[0],
                    "y": rect.position[1]
                },
                "rotated": rect.rotated,
                "dimensions_after_rotation": {
                    "width": rect.height if rect.rotated else rect.width,
                    "height": rect.width if rect.rotated else rect.height
                }
            }
            for rect in sheet.placed_rectangles
        ]
    }

def convert_results_to_json(results: dict) -> dict:
    """
    Convert optimization results to a JSON-serializable dictionary.
    
    Args:
        results (dict): Dictionary mapping glass codes to lists of Sheet objects
        
    Returns:
        dict: JSON-serializable dictionary with optimization results
    """
    json_results = {}
    
    for glass_code, sheets in results.items():
        total_sheets = len(sheets)
        total_pieces = sum(len(sheet.placed_rectangles) for sheet in sheets)
        
        # Calculate overall efficiency
        total_area = sum(sheet.width * sheet.height for sheet in sheets)
        used_area = sum(
            sum(rect.width * rect.height for rect in sheet.placed_rectangles)
            for sheet in sheets
        )
        overall_efficiency = (used_area / total_area * 100) if total_area > 0 else 0
        
        json_results[glass_code] = {
            "summary": {
                "total_sheets": total_sheets,
                "total_pieces": total_pieces,
                "overall_efficiency": round(overall_efficiency, 2),
                "total_area": total_area,
                "used_area": used_area
            },
            "sheets": [convert_sheet_to_dict(sheet) for sheet in sheets]
        }
    
    return json_results

def save_results_to_json(results: dict, filename: str):
    """
    Save optimization results to a JSON file.
    
    Args:
        results (dict): Optimization results in JSON format
        filename (str): Output filename
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

# Example usage
def main():
    # Initialize inventory
    # df = get_produccion()
    # df = pd.read_csv("/Users/guzma/Documents/Veca/code/templado/reportes/produccion.csv") 
    # df = process_dataframe(df)
    # df = df[["Ped","ITEM", "Esp", "Largo", "Ancho", "Pzs."]]
    # optimizer_numbers = [
    #     27887, 27935,
    #     27968, 27946, 
    #     27948, 27945,
    #     27965, 27969,
    #     27956, 27952,
    #     27946, 27951,
    #     27958, 27953,
    #     27948, 27965,
    #     27949, 27967,
    #     27966
    # ]
    # df = df[df["Ped"].isin(optimizer_numbers)]
    # df.drop(columns=["Ped"], inplace=True)
    # print(df)
    data = {
   'ITEM': ['CL10', 'CL10'],
   'Esp': [10, 10], 
   'Largo': [1167, 1178],
   'Ancho': [2180, 1167],
   'Pzs.': [17, 18]
}

    df = pd.DataFrame(data)

    # df = pd.read_excel("LISTA DE VIDRIO LORETO TOWER.xlsx", sheet_name="BARANDALES N2")
    # print(df)

    data = reduce_to_same_glass(df, return_json=True, use_existing=True)

    inventory = GlassInventory()
    optimizer = GlassCuttingOptimizer(inventory)
    
    # Example cutting list for CL6 glass
    transformed_data = transform_glass_data(data)
    
    # Run optimization for all glass types
    results = optimize_all_glass(transformed_data, optimizer, output_json=True)

    # Save results to JSON file
    save_results_to_json(results, "glass_optimization_results.json")
    
    # Print summary
    print("\nOptimization complete! Results saved to glass_optimization_results.json")
    for glass_code, result in results.items():
        print(f"\nSummary for {glass_code}:")
        print(f"Total sheets required: {result['summary']['total_sheets']}")
        print(f"Overall efficiency: {result['summary']['overall_efficiency']}%")


if __name__ == "__main__":
    main()