import os
import json
import asyncio
import copy

DATABASE_FILE = "database.json"

def match_value(actual, expected) -> bool:
    if isinstance(expected, dict):
        if "$gt" in expected:
            return actual > expected["$gt"]
        if "$lt" in expected:
            return actual < expected["$lt"]
        if "$ne" in expected:
            return actual != expected["$ne"]
    if isinstance(actual, list):
        return expected in actual or any(match_value(x, expected) for x in actual)
    return actual == expected


def get_values_by_path(value, parts):
    if not parts:
        return [value]
    field = parts[0]
    if isinstance(value, dict):
        if field in value:
            return get_values_by_path(value[field], parts[1:])
        return []
    elif isinstance(value, list):
        res = []
        for item in value:
            res.extend(get_values_by_path(item, parts))
        return res
    return []


def match_document(doc, query) -> bool:
    if not query:
        return True
    for key, val in query.items():
        if "." in key:
            parts = key.split(".")
            actual_vals = get_values_by_path(doc, parts)
            if not actual_vals:
                return False
            if not any(match_value(act, val) for act in actual_vals):
                return False
        else:
            if key not in doc:
                return False
            if not match_value(doc[key], val):
                return False
    return True


def find_positional_index(doc, query):
    for key, val in query.items():
        if '.' in key:
            parts = key.split('.')
            if len(parts) == 2:
                array_field, sub_field = parts
                if array_field in doc and isinstance(doc[array_field], list):
                    for i, item in enumerate(doc[array_field]):
                        if isinstance(item, dict) and sub_field in item:
                            if match_value(item[sub_field], val):
                                return i
    return None


def set_nested_value(doc, parts, value):
    parts = [int(p) if p.isdigit() else p for p in parts]
    current = doc
    for p in parts[:-1]:
        if isinstance(current, dict):
            if p not in current:
                current[p] = {}
            current = current[p]
        elif isinstance(current, list):
            current = current[p]
    last_p = parts[-1]
    if isinstance(current, dict):
        current[last_p] = value
    elif isinstance(current, list):
        current[last_p] = value


def push_nested_value(doc, parts, value):
    parts = [int(p) if p.isdigit() else p for p in parts]
    current = doc
    for p in parts[:-1]:
        if isinstance(current, dict):
            if p not in current:
                current[p] = {}
            current = current[p]
        elif isinstance(current, list):
            current = current[p]
    last_p = parts[-1]
    if isinstance(current, dict):
        if last_p not in current or current[last_p] is None:
            current[last_p] = []
        if isinstance(current[last_p], list):
            current[last_p].append(value)


def pull_nested_value(doc, parts, condition):
    parts = [int(p) if p.isdigit() else p for p in parts]
    current = doc
    for p in parts[:-1]:
        if isinstance(current, dict):
            if p not in current:
                return
            current = current[p]
        elif isinstance(current, list):
            current = current[p]
    last_p = parts[-1]
    if isinstance(current, dict) and last_p in current and isinstance(current[last_p], list):
        arr = current[last_p]
        new_arr = []
        for item in arr:
            if isinstance(condition, dict):
                match = True
                for ck, cv in condition.items():
                    if isinstance(item, dict):
                        if item.get(ck) != cv:
                            match = False
                            break
                    else:
                        match = False
                        break
                if not match:
                    new_arr.append(item)
            else:
                if item != condition:
                    new_arr.append(item)
        current[last_p] = new_arr


def add_to_set_nested_value(doc, parts, value):
    parts = [int(p) if p.isdigit() else p for p in parts]
    current = doc
    for p in parts[:-1]:
        if isinstance(current, dict):
            if p not in current:
                current[p] = {}
            current = current[p]
        elif isinstance(current, list):
            current = current[p]
    last_p = parts[-1]
    if isinstance(current, dict):
        if last_p not in current or current[last_p] is None:
            current[last_p] = []
        if isinstance(current[last_p], list):
            if value not in current[last_p]:
                current[last_p].append(value)


def unset_nested_value(doc, parts):
    parts = [int(p) if p.isdigit() else p for p in parts]
    current = doc
    for p in parts[:-1]:
        if isinstance(current, dict):
            if p not in current:
                return
            current = current[p]
        elif isinstance(current, list):
            current = current[p]
    last_p = parts[-1]
    if isinstance(current, dict):
        current.pop(last_p, None)
    elif isinstance(current, list):
        if isinstance(last_p, int) and 0 <= last_p < len(current):
            current.pop(last_p)


def apply_update(doc, update_spec, query=None):
    positional_index = None
    if query:
        positional_index = find_positional_index(doc, query)

    for op, spec in update_spec.items():
        if op == "$set":
            for path_str, val in spec.items():
                p_str = path_str
                if positional_index is not None:
                    p_str = p_str.replace('$', str(positional_index))
                parts = p_str.split('.')
                set_nested_value(doc, parts, val)
        elif op == "$push":
            for path_str, val in spec.items():
                p_str = path_str
                if positional_index is not None:
                    p_str = p_str.replace('$', str(positional_index))
                parts = p_str.split('.')
                push_nested_value(doc, parts, val)
        elif op == "$pull":
            for path_str, val in spec.items():
                p_str = path_str
                if positional_index is not None:
                    p_str = p_str.replace('$', str(positional_index))
                parts = p_str.split('.')
                pull_nested_value(doc, parts, val)
        elif op == "$addToSet":
            for path_str, val in spec.items():
                p_str = path_str
                if positional_index is not None:
                    p_str = p_str.replace('$', str(positional_index))
                parts = p_str.split('.')
                add_to_set_nested_value(doc, parts, val)
        elif op == "$unset":
            for path_str, val in spec.items():
                p_str = path_str
                if positional_index is not None:
                    p_str = p_str.replace('$', str(positional_index))
                parts = p_str.split('.')
                unset_nested_value(doc, parts)


class JSONCursor:
    def __init__(self, results):
        self.results = results
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.results):
            raise StopAsyncIteration
        res = self.results[self.index]
        self.index += 1
        return res

    async def to_list(self, length=None):
        if length is not None:
            return self.results[:length]
        return self.results


class JSONCollection:
    def __init__(self, db_client, collection_name):
        self.db_client = db_client
        self.name = collection_name

    def __getitem__(self, item):
        return JSONCollection(self.db_client, f"{self.name}.{item}")

    def _get_data(self):
        if self.name not in self.db_client._data:
            self.db_client._data[self.name] = []
        return self.db_client._data[self.name]

    async def find_one(self, query):
        data = self._get_data()
        for doc in data:
            if match_document(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query):
        data = self._get_data()
        results = []
        for doc in data:
            if match_document(doc, query):
                results.append(copy.deepcopy(doc))
        return JSONCursor(results)

    async def insert_one(self, document):
        doc = copy.deepcopy(document)
        data = self._get_data()
        data.append(doc)
        await self.db_client.save()
        return doc

    async def delete_one(self, query):
        data = self._get_data()
        for i, doc in enumerate(data):
            if match_document(doc, query):
                data.pop(i)
                await self.db_client.save()
                return True
        return False

    async def count_documents(self, query):
        if not query:
            return len(self._get_data())
        count = 0
        for doc in self._get_data():
            if match_document(doc, query):
                count += 1
        return count

    async def update_one(self, query, update, upsert=False):
        data = self._get_data()
        found = False
        for doc in data:
            if match_document(doc, query):
                apply_update(doc, update, query)
                found = True
                break
        if not found and upsert:
            new_doc = {}
            for k, v in query.items():
                if '.' not in k and not isinstance(v, dict):
                    new_doc[k] = v
            apply_update(new_doc, update, query)
            data.append(new_doc)
        await self.db_client.save()
        return True

    async def update(self, query, update, upsert=False, multi=False):
        data = self._get_data()
        found = False
        for doc in data:
            if match_document(doc, query):
                apply_update(doc, update, query)
                found = True
                if not multi:
                    break
        if not found and upsert:
            new_doc = {}
            for k, v in query.items():
                if '.' not in k and not isinstance(v, dict):
                    new_doc[k] = v
            apply_update(new_doc, update, query)
            data.append(new_doc)
        await self.db_client.save()
        return True


class JSONDatabase:
    def __init__(self):
        self._data = {}
        self._lock = asyncio.Lock()
        self.load()

    def load(self):
        if os.path.exists(DATABASE_FILE):
            try:
                with open(DATABASE_FILE, "r") as f:
                    self._data = json.load(f)
            except Exception as e:
                print(f"Error loading {DATABASE_FILE}: {e}")
                self._data = {}
        else:
            self._data = {}

    def _write_file(self, temp_file):
        with open(temp_file, "w") as f:
            json.dump(self._data, f, indent=4)
        os.replace(temp_file, DATABASE_FILE)

    async def save(self):
        async with self._lock:
            temp_file = f"{DATABASE_FILE}.tmp"
            try:
                await asyncio.to_thread(self._write_file, temp_file)
            except Exception as e:
                print(f"Error saving database to JSON: {e}")

    def __getattr__(self, name):
        return JSONCollection(self, name)

    def __getitem__(self, name):
        return JSONCollection(self, name)

    async def command(self, cmd_name):
        if cmd_name == "dbstats":
            data_str = json.dumps(self._data)
            return {
                "dataSize": len(data_str),
                "storageSize": len(data_str),
                "collections": len(self._data),
                "objects": sum(len(v) for v in self._data.values() if isinstance(v, list)),
            }
        return {}
