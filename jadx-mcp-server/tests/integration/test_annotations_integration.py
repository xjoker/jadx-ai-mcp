"""
Layer 3 Integration Tests - Annotation/Bookmark/Tag APIs

Tests the collaborative analysis note endpoints exposed by AnnotationRoutes.
Each test uses a unique apk_hash to avoid leaking state across runs because the
backing SQLite database persists between test sessions.
"""

from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration

TEST_CLASS = "com.jadxtest.library.Calculator"
ALT_TEST_CLASS = "com.jadxtest.library.StringUtils"
TEST_TARGET_TYPE = "class"


def _unique_apk_hash(prefix: str) -> str:
    return f"it-{prefix}-{uuid4().hex}"


def _find_by_id(items: list[dict], expected_id: int) -> dict | None:
    for item in items:
        if item.get("id") == expected_id:
            return item
    return None


async def _create_annotation(http_client, jadx_base_url, *, apk_hash: str, target_name: str, content: str):
    return await http_client.post(
        f"{jadx_base_url}/annotations",
        json={
            "apk_hash": apk_hash,
            "target_type": TEST_TARGET_TYPE,
            "target_name": target_name,
            "content": content,
            "author": "integration-test",
        },
    )


async def _create_bookmark(
    http_client,
    jadx_base_url,
    *,
    apk_hash: str,
    target_name: str,
    label: str,
    note: str,
):
    return await http_client.post(
        f"{jadx_base_url}/bookmarks",
        json={
            "apk_hash": apk_hash,
            "target_type": TEST_TARGET_TYPE,
            "target_name": target_name,
            "label": label,
            "note": note,
            "author": "integration-test",
        },
    )


async def _create_tag(http_client, jadx_base_url, *, apk_hash: str, target_name: str, tag: str):
    return await http_client.post(
        f"{jadx_base_url}/tags",
        json={
            "apk_hash": apk_hash,
            "target_type": TEST_TARGET_TYPE,
            "target_name": target_name,
            "tag": tag,
            "author": "integration-test",
        },
    )


async def _delete_resource(http_client, jadx_base_url, resource: str, resource_id: int) -> None:
    resp = await http_client.delete(f"{jadx_base_url}/{resource}/{resource_id}")
    assert resp.status_code in {200, 404}, (
        f"Unexpected cleanup status for {resource}/{resource_id}: {resp.status_code}"
    )


@pytest.mark.asyncio
class TestAnnotationsCRUD:
    async def test_annotations_crud(self, jadx_base_url, http_client):
        apk_hash = _unique_apk_hash("annotations")
        created_ids: list[int] = []

        try:
            create_resp = await _create_annotation(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=TEST_CLASS,
                content="test note",
            )
            assert create_resp.status_code == 201
            created = create_resp.json()
            annotation_id = created["id"]
            created_ids.append(annotation_id)
            assert annotation_id > 0

            second_resp = await _create_annotation(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=ALT_TEST_CLASS,
                content="other note",
            )
            assert second_resp.status_code == 201
            second_annotation_id = second_resp.json()["id"]
            created_ids.append(second_annotation_id)

            list_resp = await http_client.get(
                f"{jadx_base_url}/annotations",
                params={"apk_hash": apk_hash},
            )
            assert list_resp.status_code == 200
            annotations = list_resp.json()["annotations"]

            created_annotation = _find_by_id(annotations, annotation_id)
            assert created_annotation is not None
            assert created_annotation["target_type"] == TEST_TARGET_TYPE
            assert created_annotation["target_name"] == TEST_CLASS
            assert created_annotation["content"] == "test note"

            filtered_resp = await http_client.get(
                f"{jadx_base_url}/annotations",
                params={
                    "apk_hash": apk_hash,
                    "target_type": TEST_TARGET_TYPE,
                    "target_name": TEST_CLASS,
                },
            )
            assert filtered_resp.status_code == 200
            filtered_annotations = filtered_resp.json()["annotations"]
            filtered_ids = {item["id"] for item in filtered_annotations}

            assert annotation_id in filtered_ids
            assert second_annotation_id not in filtered_ids

            delete_resp = await http_client.delete(f"{jadx_base_url}/annotations/{annotation_id}")
            assert delete_resp.status_code == 200
            assert delete_resp.json()["deleted_id"] == annotation_id
            created_ids.remove(annotation_id)

            after_delete_resp = await http_client.get(
                f"{jadx_base_url}/annotations",
                params={"apk_hash": apk_hash},
            )
            assert after_delete_resp.status_code == 200
            after_delete_annotations = after_delete_resp.json()["annotations"]
            after_delete_ids = {item["id"] for item in after_delete_annotations}

            assert annotation_id not in after_delete_ids
            assert second_annotation_id in after_delete_ids

            after_delete_filtered_resp = await http_client.get(
                f"{jadx_base_url}/annotations",
                params={
                    "apk_hash": apk_hash,
                    "target_type": TEST_TARGET_TYPE,
                    "target_name": TEST_CLASS,
                },
            )
            assert after_delete_filtered_resp.status_code == 200
            assert _find_by_id(after_delete_filtered_resp.json()["annotations"], annotation_id) is None
        finally:
            for created_id in created_ids:
                await _delete_resource(http_client, jadx_base_url, "annotations", created_id)


@pytest.mark.asyncio
class TestBookmarksCRUD:
    async def test_bookmarks_crud(self, jadx_base_url, http_client):
        apk_hash = _unique_apk_hash("bookmarks")
        bookmark_id: int | None = None

        try:
            create_resp = await _create_bookmark(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=TEST_CLASS,
                label="entry-point",
                note="main entry",
            )
            assert create_resp.status_code == 201
            created = create_resp.json()
            bookmark_id = created["id"]
            assert bookmark_id > 0

            list_resp = await http_client.get(
                f"{jadx_base_url}/bookmarks",
                params={"apk_hash": apk_hash},
            )
            assert list_resp.status_code == 200
            bookmarks = list_resp.json()["bookmarks"]

            bookmark = _find_by_id(bookmarks, bookmark_id)
            assert bookmark is not None
            assert bookmark["label"] == "entry-point"
            assert bookmark["note"] == "main entry"
            assert bookmark["target_name"] == TEST_CLASS

            delete_resp = await http_client.delete(f"{jadx_base_url}/bookmarks/{bookmark_id}")
            assert delete_resp.status_code == 200
            assert delete_resp.json()["deleted_id"] == bookmark_id
            bookmark_id = None

            after_delete_resp = await http_client.get(
                f"{jadx_base_url}/bookmarks",
                params={"apk_hash": apk_hash},
            )
            assert after_delete_resp.status_code == 200
            assert _find_by_id(after_delete_resp.json()["bookmarks"], create_resp.json()["id"]) is None
        finally:
            if bookmark_id is not None:
                await _delete_resource(http_client, jadx_base_url, "bookmarks", bookmark_id)


@pytest.mark.asyncio
class TestTagsCRUD:
    async def test_tags_crud(self, jadx_base_url, http_client):
        apk_hash = _unique_apk_hash("tags")
        created_ids: list[int] = []

        try:
            create_resp = await _create_tag(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=TEST_CLASS,
                tag="crypto",
            )
            assert create_resp.status_code == 201
            created_tag_id = create_resp.json()["id"]
            created_ids.append(created_tag_id)

            second_resp = await _create_tag(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=ALT_TEST_CLASS,
                tag="network",
            )
            assert second_resp.status_code == 201
            second_tag_id = second_resp.json()["id"]
            created_ids.append(second_tag_id)

            list_resp = await http_client.get(
                f"{jadx_base_url}/tags",
                params={"apk_hash": apk_hash},
            )
            assert list_resp.status_code == 200
            tags = list_resp.json()["tags"]

            created_tag = _find_by_id(tags, created_tag_id)
            assert created_tag is not None
            assert created_tag["tag"] == "crypto"
            assert created_tag["target_name"] == TEST_CLASS

            filtered_resp = await http_client.get(
                f"{jadx_base_url}/tags",
                params={"apk_hash": apk_hash, "tag": "crypto"},
            )
            assert filtered_resp.status_code == 200
            filtered_tags = filtered_resp.json()["tags"]
            filtered_ids = {item["id"] for item in filtered_tags}

            assert created_tag_id in filtered_ids
            assert second_tag_id not in filtered_ids

            delete_resp = await http_client.delete(f"{jadx_base_url}/tags/{created_tag_id}")
            assert delete_resp.status_code == 200
            assert delete_resp.json()["deleted_id"] == created_tag_id
            created_ids.remove(created_tag_id)
        finally:
            for created_id in created_ids:
                await _delete_resource(http_client, jadx_base_url, "tags", created_id)


@pytest.mark.asyncio
class TestAnalysisNotesSummary:
    async def test_analysis_notes_summary_includes_all_data(self, jadx_base_url, http_client):
        apk_hash = _unique_apk_hash("analysis-notes")
        annotation_id: int | None = None
        bookmark_id: int | None = None
        tag_id: int | None = None

        try:
            annotation_resp = await _create_annotation(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=TEST_CLASS,
                content="summary note",
            )
            assert annotation_resp.status_code == 201
            annotation_id = annotation_resp.json()["id"]

            bookmark_resp = await _create_bookmark(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=TEST_CLASS,
                label="entry-point",
                note="summary bookmark",
            )
            assert bookmark_resp.status_code == 201
            bookmark_id = bookmark_resp.json()["id"]

            tag_resp = await _create_tag(
                http_client,
                jadx_base_url,
                apk_hash=apk_hash,
                target_name=TEST_CLASS,
                tag="crypto",
            )
            assert tag_resp.status_code == 201
            tag_id = tag_resp.json()["id"]

            summary_resp = await http_client.get(
                f"{jadx_base_url}/analysis-notes",
                params={"apk_hash": apk_hash},
            )
            assert summary_resp.status_code == 200

            data = summary_resp.json()
            assert data["apk_hash"] == apk_hash
            assert data["annotations_count"] == 1
            assert data["bookmarks_count"] == 1
            assert data["tags_count"] == 1

            assert _find_by_id(data["annotations"], annotation_id) is not None
            assert _find_by_id(data["bookmarks"], bookmark_id) is not None
            assert _find_by_id(data["tags"], tag_id) is not None
        finally:
            if annotation_id is not None:
                await _delete_resource(http_client, jadx_base_url, "annotations", annotation_id)
            if bookmark_id is not None:
                await _delete_resource(http_client, jadx_base_url, "bookmarks", bookmark_id)
            if tag_id is not None:
                await _delete_resource(http_client, jadx_base_url, "tags", tag_id)


@pytest.mark.asyncio
class TestAnnotationEdgeCases:
    async def test_post_annotations_missing_required_field_returns_400(self, jadx_base_url, http_client):
        resp = await http_client.post(
            f"{jadx_base_url}/annotations",
            json={
                "target_type": TEST_TARGET_TYPE,
                "target_name": TEST_CLASS,
            },
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    async def test_delete_missing_annotation_returns_404(self, jadx_base_url, http_client):
        resp = await http_client.delete(f"{jadx_base_url}/annotations/9223372036854775807")
        assert resp.status_code == 404
        assert "not found" in resp.json()["error"].lower()

    async def test_post_bookmarks_missing_label_returns_400(self, jadx_base_url, http_client):
        resp = await http_client.post(
            f"{jadx_base_url}/bookmarks",
            json={
                "target_type": TEST_TARGET_TYPE,
                "target_name": TEST_CLASS,
                "note": "missing label",
            },
        )
        assert resp.status_code == 400
        assert "label is required" in resp.json()["error"]
