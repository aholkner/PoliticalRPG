from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.namespaces import TABLENS

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
                db_value = '\n'.join(map(str, cell.getElementsByType(P))).decode('utf-8')
                db_value = db_value.strip()
                try:
                    db_value = float(db_value)
                except:
                    db_value = db_value.replace(u'\u2026', '...')
                    db_value = db_value.encode('utf-8')
                
                try:
                    repeat_count = int(cell.getAttribute('numbercolumnsrepeated'))
                except:
                    repeat_count = 1

                if not cell.nextSibling:
                    repeat_count = 1
                for i in range(repeat_count):
                    db_row.append(db_value)

    return db
         