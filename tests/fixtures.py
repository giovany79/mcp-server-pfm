import io


SAMPLE_CSV = """Description;Income/expensive;Amount;Category;Date;transaction_id
salary;income;5000;salary;2025-01-01;tx-income-jan
rent;expensive;1200;home;2025-01-02;tx-rent-jan
restaurant dinner;expensive;150;restaurant;2025-01-03;tx-food-jan
trip tickets;expensive;800;vacaciones;2025-02-05;tx-vac-feb
bonus;income;1000;salary;2025-02-10;tx-income-feb
book;expensive;40;education;2026-01-01;tx-book-2026
"""


SAMPLE_CSV_WITHOUT_IDS = """ Description ;Income/expensive;Amount;Category;Date
salary;income;$ 5.000;salary;01/01/2025
rent;expensive;1.200;home;02/01/2025
invalid amount;expensive;not-a-number;home;03/01/2025
invalid date;expensive;100;home;bad-date
"""


SAMPLE_BALANCE_SHEET_CSV = """item_id;snapshot_date;name;kind;category;amount;currency;institution;notes
asset-cash-jan;2025-01-31;Cuenta ahorros;asset;cash;10000;COP;Bancolombia;
asset-invest-jan;2025-01-31;Inversiones;asset;investments;30000;COP;;
liability-card-jan;2025-01-31;Tarjeta credito;liability;credit_card;5000;COP;Visa;
asset-cash-feb;2025-02-28;Cuenta ahorros;asset;cash;12000;COP;Bancolombia;
asset-invest-feb;2025-02-28;Inversiones;asset;investments;32000;COP;;
liability-card-feb;2025-02-28;Tarjeta credito;liability;credit_card;4000;COP;Visa;
"""


class Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3:
    def __init__(self, csv_text: str, objects=None):
        self.csv_text = csv_text
        self.objects = {"pfm-gio.csv": csv_text}
        if objects:
            self.objects.update(objects)
        self.put_calls = []

    def get_object(self, Bucket: str, Key: str):
        if Key not in self.objects:
            error = Exception("NoSuchKey")
            error.response = {"Error": {"Code": "NoSuchKey"}}
            raise error
        return {"Body": Body(self.objects[Key].encode("utf-8"))}

    def put_object(self, Bucket: str, Key: str, Body: bytes):
        text = Body.decode("utf-8")
        self.objects[Key] = text
        if Key == "pfm-gio.csv":
            self.csv_text = text
        self.put_calls.append({"Bucket": Bucket, "Key": Key, "Body": Body})


def read_csv_text(path) -> str:
    with io.open(path, "r", encoding="utf-8") as file:
        return file.read()
