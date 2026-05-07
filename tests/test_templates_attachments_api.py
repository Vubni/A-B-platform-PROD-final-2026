from aiohttp import FormData


async def _create_draft_experiment(
    http_session,
    base_url,
    auth_headers_experimenter,
    flag_id,
    name="Attachment test experiment",
):
    async with http_session.post(
        f"{base_url}/api/v1/experiments",
        headers=auth_headers_experimenter,
        json={"flag_id": flag_id, "name": name, "audience_fraction": 0.5},
    ) as resp:
        assert resp.status == 201, await resp.text()
        return await resp.json()


async def test_experiment_attachment_upload_list_download_delete(
    http_session,
    base_url,
    auth_headers_experimenter,
    flag_id,
):
    experiment = await _create_draft_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        flag_id,
    )
    exp_id = experiment["id"]

    form = FormData()
    form.add_field("description", "Sample-size notes")
    form.add_field(
        "file",
        b"subject_id,variant\nu1,control\n",
        filename="sample-size.csv",
        content_type="text/csv",
    )

    async with http_session.post(
        f"{base_url}/api/v1/experiments/{exp_id}/attachments",
        headers=auth_headers_experimenter,
        data=form,
    ) as resp:
        assert resp.status == 201, await resp.text()
        attachment = await resp.json()
    attachment_id = attachment["id"]
    assert attachment["original_filename"] == "sample-size.csv"
    assert attachment["size_bytes"] > 0

    async with http_session.get(
        f"{base_url}/api/v1/experiments/{exp_id}/attachments",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
    assert any(item["id"] == attachment_id for item in data["attachments"])

    async with http_session.get(
        f"{base_url}/api/v1/experiments/{exp_id}/attachments/{attachment_id}",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200, await resp.text()
        body = await resp.text()
    assert "subject_id,variant" in body

    async with http_session.delete(
        f"{base_url}/api/v1/experiments/{exp_id}/attachments/{attachment_id}",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 204, await resp.text()


async def test_experiment_report_html_template(
    http_session,
    base_url,
    auth_headers_experimenter,
    flag_id,
):
    experiment = await _create_draft_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        flag_id,
        name="HTML report template test",
    )
    url = (
        f"{base_url}/api/v1/experiments/{experiment['id']}/report/html"
        "?start=2026-01-01T00:00:00Z&end=2026-01-02T00:00:00Z"
    )
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200, await resp.text()
        html = await resp.text()
    assert "<html" in html
    assert "HTML report template test" in html
