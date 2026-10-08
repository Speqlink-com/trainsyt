       )
>       training = await create_programme(client, trainer, starts_in_minutes=30)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_training_attendance.py:230: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
tests/test_training_attendance.py:56: in create_programme
    headers=csrf_headers(client),
            ^^^^^^^^^^^^^^^^^^^^
tests/test_training_attendance.py:21: in csrf_headers
    return {settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]}
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <Cookies[]>, name = 'csrf_token'

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
>           raise KeyError(name)
E           KeyError: 'csrf_token'

.venv/lib/python3.12/site-packages/httpx/_models.py:1216: KeyError
---------------------------- Captured stderr setup -----------------------------
2026-10-08 18:07:15,690 INFO app.scripts.seed_admin Created seed administrator: admin@example.com
------------------------------ Captured log setup ------------------------------
INFO     app.scripts.seed_admin:seed_admin.py:65 Created seed administrator: admin@example.com
----------------------------- Captured stderr call -----------------------------
2026-10-08 18:07:16,243 INFO httpx HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
__________________ test_admin_can_update_and_delete_programme __________________

client = <httpx.AsyncClient object at 0x7fb0f03f46b0>

    async def test_admin_can_update_and_delete_programme(client: AsyncClient) -> None:
        trainer = await create_trainer("crud-trainer@example.com")
        await login(
            client,
            settings.SEED_ADMIN_EMAIL or "",
            settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
        )
>       training = await create_programme(client, trainer)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_training_attendance.py:266: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
tests/test_training_attendance.py:56: in create_programme
    headers=csrf_headers(client),
            ^^^^^^^^^^^^^^^^^^^^
tests/test_training_attendance.py:21: in csrf_headers
    return {settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]}
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <Cookies[]>, name = 'csrf_token'

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
>           raise KeyError(name)
E           KeyError: 'csrf_token'

.venv/lib/python3.12/site-packages/httpx/_models.py:1216: KeyError
---------------------------- Captured stderr setup -----------------------------
2026-10-08 18:07:16,629 INFO app.scripts.seed_admin Created seed administrator: admin@example.com
------------------------------ Captured log setup ------------------------------
INFO     app.scripts.seed_admin:seed_admin.py:65 Created seed administrator: admin@example.com
----------------------------- Captured stderr call -----------------------------
2026-10-08 18:07:17,182 INFO httpx HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
____________ test_trainer_only_sees_and_exports_assigned_programmes ____________

client = <httpx.AsyncClient object at 0x7fb0f03f6ea0>

    async def test_trainer_only_sees_and_exports_assigned_programmes(client: AsyncClient) -> None:
        assigned_trainer = await create_trainer("assigned@example.com")
        other_trainer = await create_trainer("other@example.com")
        await login(
            client,
            settings.SEED_ADMIN_EMAIL or "",
            settings.SEED_ADMIN_PASSWORD.get_secret_value() if settings.SEED_ADMIN_PASSWORD else "",
        )
>       training = await create_programme(client, assigned_trainer)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_training_attendance.py:364: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
tests/test_training_attendance.py:56: in create_programme
    headers=csrf_headers(client),
            ^^^^^^^^^^^^^^^^^^^^
tests/test_training_attendance.py:21: in csrf_headers
    return {settings.CSRF_HEADER_NAME: client.cookies[settings.CSRF_COOKIE_NAME]}
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <Cookies[]>, name = 'csrf_token'

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
>           raise KeyError(name)
E           KeyError: 'csrf_token'

.venv/lib/python3.12/site-packages/httpx/_models.py:1216: KeyError
---------------------------- Captured stderr setup -----------------------------
2026-10-08 18:07:17,573 INFO app.scripts.seed_admin Created seed administrator: admin@example.com
------------------------------ Captured log setup ------------------------------
INFO     app.scripts.seed_admin:seed_admin.py:65 Created seed administrator: admin@example.com
----------------------------- Captured stderr call -----------------------------
2026-10-08 18:07:18,399 INFO httpx HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
------------------------------ Captured log call -------------------------------
INFO     httpx:_client.py:1740 HTTP Request: POST http://testserver/api/auth/login "HTTP/1.1 200 OK"
=========================== short test summary info ============================
FAILED tests/test_auth_flow.py::test_seed_admin_is_idempotent_and_can_login - AssertionError: assert None
 +  where None = get('access_token')
 +    where get = <Cookies[]>.get
 +      where <Cookies[]> = <httpx.AsyncClient object at 0x7fb0f0a929c0>.cookies
FAILED tests/test_auth_flow.py::test_seed_admin_temporary_password_requires_immediate_change - AssertionError: assert None
 +  where None = get('temp_token')
 +    where get = <Cookies[]>.get
 +      where <Cookies[]> = <httpx.AsyncClient object at 0x7fb0f034f080>.cookies
FAILED tests/test_auth_flow.py::test_at_most_six_active_administrator_accounts - KeyError: 'csrf_token'
FAILED tests/test_auth_flow.py::test_invitation_first_login_rotation_replay_and_admin_control - KeyError: 'csrf_token'
FAILED tests/test_auth_flow.py::test_user_is_preserved_when_invitation_delivery_fails - KeyError: 'csrf_token'
FAILED tests/test_auth_flow.py::test_password_reset_uses_one_time_hashed_code - KeyError: 'csrf_token'
FAILED tests/test_training_attendance.py::test_qr_registration_attendance_and_excel_export - KeyError: 'csrf_token'
FAILED tests/test_training_attendance.py::test_one_hour_reminders_are_sent_once - KeyError: 'csrf_token'
FAILED tests/test_training_attendance.py::test_admin_can_update_and_delete_programme - KeyError: 'csrf_token'
FAILED tests/test_training_attendance.py::test_trainer_only_sees_and_exports_assigned_programmes - KeyError: 'csrf_token'
10 failed, 4 passed in 10.95s
Error: Process completed with exit code 1.
