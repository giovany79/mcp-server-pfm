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


class Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3:
    def __init__(self, csv_text: str):
        self.csv_text = csv_text
        self.put_calls = []

    def get_object(self, Bucket: str, Key: str):
        return {"Body": Body(self.csv_text.encode("utf-8"))}

    def put_object(self, Bucket: str, Key: str, Body: bytes):
        self.csv_text = Body.decode("utf-8")
        self.put_calls.append({"Bucket": Bucket, "Key": Key, "Body": Body})


def read_csv_text(path) -> str:
    with io.open(path, "r", encoding="utf-8") as file:
        return file.read()
