from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P

def import_ods(path):
    doc = load(path)

    db = {}

    tables = doc.spreadsheet.getElementsByType(Table)
    for table in tables:
        db_table = []
        db[table.getAttribute('name')] = db_table
        for row in table.getElementsByType(TableRow):
            db_row = []
            db_table.append(db_row)
            for cell in row.getElementsByType(TableCell):
                db_value = '\n'.join(map(str, cell.getElementsByType(P)))
                try:
                    db_value = float(db_value)
                except:
                    pass
                db_row.append(db_value)

    return db
         