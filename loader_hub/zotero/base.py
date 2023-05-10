"""Zotero reader."""
import os
from typing import Any, Dict, List, Optional

import requests  # type: ignore
import urllib
from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document

USER_ID_NAME = "ZOTERO_USER_ID"
PRIVATE_KEY_NAME = "ZOTERO_PRIVATE_KEY"
BASE_URL = "https://api.zotero.org"


class ZoteroItemReader(BaseReader):
    """Zotero Item reader.

    Reads a set of Zotero pages.

    Args:
        private_key (str): Zotero private key.

    """

    def __init__(self, user_id: Optional[str] = None, private_key: Optional[str] = None) -> None:
        """Initialize with parameters."""
        if user_id is None:
            user_id = os.getenv(USER_ID_NAME)
            if user_id is None:
                raise ValueError(
                    "Must specify `user_id` or set environment "
                    "variable `ZOTERO_USER_ID`."
                )
        if private_key is None:
            private_key = os.getenv(PRIVATE_KEY_NAME)
            if private_key is None:
                raise ValueError(
                    "Must specify `private_key` or set environment "
                    "variable `ZOTERO_PRIVATE_KEY`."
                )
        # TODO: Support group libraries as well.
        self.user_id = user_id
        self.private_key = private_key
        # API Request format information:
        # https://www.zotero.org/support/dev/web_api/v3/basics
        self.headers = {
            "Authorization": "Bearer " + self.private_key,
            "Zotero-API-Version": "3",
        }

    def _read_item(self, item_url: str, num_tabs: int = 0) -> str:
        """Read the full text of an item."""
        text_url = f"{item_url}/fulltext"
        res = requests.get(
            text_url,
            headers={
                **self.headers,
                "Content-Type": "application/json",
            },
        )
        res.raise_for_status()
        data = res.json()
        return data["content"]

    def read_item(self, item_url: str) -> str:
        """Read a page."""
        return self._read_item(item_url)

    def query_urls(
            self,
            collection_id: Optional[str] = None,
            query_dict: Dict[str, Any] = {"page_size": 100},
        ) -> List[str]:
        """Get all the pages from a Zotero database."""
        items = []

        start_url = f"{BASE_URL}/users/{self.user_id}/items"
        if collection_id is not None:
            start_url = f"{BASE_URL}/users/{self.user_id}/collections/{collection_id}/items"

        res = requests.get(
            start_url,
            headers=self.headers,
            params=query_dict,
        )
        res.raise_for_status()
        data = res.json()

        items.extend(data)

        while "next" in res.links:
            next_url = res.links["next"]["url"]
            res = requests.get(
                next_url,
                headers=self.headers,
            )
            res.raise_for_status()
            data = res.json()
            items.extend(data)

        item_urls = [item["links"]["attachment"]["href"] for item in items if "attachment" in item["links"]]
        return item_urls

    def search(self, query: str) -> List[str]:
        """Search Zotero documents given a text query."""
        done = False
        next_url: Optional[str] = None
        item_urls = []
        while not done:
            if next_url is None:
                q = urllib.parse.quote(query)
                next_url = f"{BASE_URL}/users/{self.user_id}/items?q={q}"
            res = requests.get(next_url, headers=self.headers)
            data = res.json()
            for item in data:
                if "attachment" in item["links"]:
                    item_urls.append(item["links"]["attachment"]["href"])

            if "next" not in res.links:
                done = True
                break
            else:
                next_url = res.links["next"]
                break
        return item_urls

    def load_data(
        self, item_urls: List[str] = [], collection_id: Optional[str] = None
    ) -> List[Document]:
        """Load data from the desired locations. If neither parameter is specified
        then data is loaded from the entire library.

        Args:
            item_urls (List[str]): List of items keys to load.
            collection_id (str): Collection ID from which to load item keys.

        Returns:
            List[Document]: List of documents.

        """
        docs = []
        if collection_id is not None:
            # get all the pages in the database
            item_urls = self.query_urls(collection_id)
        elif len(item_urls) == 0:
            # get all the pages in the library
            item_urls = self.query_urls()

        for item_url in item_urls:
            item_text = self.read_item(item_url)
            docs.append(Document(item_text, extra_info={"item_key": item_url}))

        return docs


if __name__ == "__main__":
    reader = ZoteroItemReader()
    item_urls = reader.search("GPT")
    print(item_urls)
    items = reader.load_data(item_urls=item_urls)
    print(items)
