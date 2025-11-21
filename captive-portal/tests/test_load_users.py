import backend.auth as auth

def test_load_users(tmp_path):
    # Crea un archivo temporal con usuarios
    userfile = tmp_path / "users.txt"
    userfile.write_text("alice:password123\nbob:secret\n#comentario\n")
    auth.load_users(str(userfile))
    assert auth.USERS["alice"] == "password123"
    assert auth.USERS["bob"] == "secret"
