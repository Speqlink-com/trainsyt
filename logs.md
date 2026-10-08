8s
.venv/lib/python3.12/site-packages/sqlalchemy/util/_concurrency_py3k.py:196: in greenlet_spawn
    value = await result
            ^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/aiosqlite/core.py:168: in _connect
    self._connection = await future
                       ^^^^^^^^^^^^
.venv/lib/python3.12/site-packages/aiosqlite/core.py:63: in _connection_worker_thread
    result = function()
             ^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

    def connector() -> sqlite3.Connection:
        if isinstance(database, str):
            loc = database
        elif isinstance(database, bytes):
            loc = database.decode("utf-8")
        else:
            loc = str(database)
    
>       return sqlite3.connect(loc, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
E       (Background on this error at: https://sqlalche.me/e/20/e3q8)

.venv/lib/python3.12/site-packages/aiosqlite/core.py:466: OperationalError
=========================== short test summary info ============================
ERROR tests/test_auth_flow.py::test_seed_admin_is_idempotent_and_can_login - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_auth_flow.py::test_seed_admin_temporary_password_requires_immediate_change - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_auth_flow.py::test_at_most_six_active_administrator_accounts - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_auth_flow.py::test_invitation_first_login_rotation_replay_and_admin_control - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_auth_flow.py::test_user_is_preserved_when_invitation_delivery_fails - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_auth_flow.py::test_password_reset_uses_one_time_hashed_code - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_email_service.py::test_console_delivery_does_not_open_smtp - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_email_service.py::test_temporary_password_template_escapes_user_content - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_email_service.py::test_training_reminder_contains_local_time_and_programme_link - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_security.py::test_temporary_password_has_four_letters_and_two_special_characters - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_training_attendance.py::test_qr_registration_attendance_and_excel_export - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_training_attendance.py::test_one_hour_reminders_are_sent_once - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_training_attendance.py::test_admin_can_update_and_delete_programme - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
ERROR tests/test_training_attendance.py::test_trainer_only_sees_and_exports_assigned_programmes - sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
(Background on this error at: https://sqlalche.me/e/20/e3q8)
14 errors in 5.23s
Error: Process completed with exit code 1.
0s
