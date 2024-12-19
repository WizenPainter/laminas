def extract_thickness(item):
    """
    Extract glass thickness from item code.
    Examples:
    - CC06T -> 6
    - CC10T -> 10
    - CMTB6T -> 6
    """
    if not isinstance(item, str):
        return None
    
    # Remove any trailing 'T' (Templado)
    item = item.rstrip('T')
    
    # Try to find a number in the item code
    digits = ''
    for char in item:
        if char.isdigit():
            digits += char
    
    # Convert to integer if found, else return None
    try:
        if digits:
            return int(digits)
        return None
    except ValueError:
        return None
    
def transform_item_name(item):
    """
    Transform item names to new format.
    Examples:
    - CC06T -> CL6
    - CC10T -> CL10
    - CC06 -> CL6
    - CSLCL06T -> CL6
    """
    if not isinstance(item, str):
        return item
        
    # Get the thickness number
    thickness = extract_thickness(item)
    if thickness is None:
        return item
        
    # Create new format
    return f"CL{thickness}"

def process_dataframe(df):
    """
    Process the dataframe to:
    1. Add Esp (thickness) column
    2. Transform ITEM names to new format
    """
    # Add thickness column
    df['Esp'] = df['ITEM'].apply(extract_thickness)
    
    # Transform ITEM names
    df['ITEM'] = df['ITEM'].apply(transform_item_name)
    
    return df

# Read the CSV file
def add_thickness_column(df):
    """
    Add Esp (thickness) column to the dataframe based on ITEM values
    """
    # Create the new Esp column
    df['Esp'] = df['ITEM'].apply(extract_thickness)
    return df