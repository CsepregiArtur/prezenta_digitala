from sqlalchemy import select
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox
from app.auth import AuthService
from app.database.models import User
from app.i18n import t, localize_window

class AdminLoginDialog(QDialog):
    """First run creates the administrator; later starts require that admin login."""
    def __init__(self, db):
        super().__init__(); self.db=db; self.auth=AuthService(db)
        with db.session() as s: self.first_run=s.scalar(select(User)) is None
        self.setWindowTitle('Attendance Control — Administrator Setup' if self.first_run else 'Attendance Control — Admin Login')
        form=QFormLayout(self); form.addRow(QLabel('Create the first administrator.' if self.first_run else 'Administrator authentication is required.'))
        self.username=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password);form.addRow(t('Username'),self.username);form.addRow(t('Password'),self.password)
        if self.first_run:
            self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.Password);form.addRow(t('Confirm password'),self.confirm)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText(t('Create administrator' if self.first_run else 'Login'));buttons.accepted.connect(self.submit);buttons.rejected.connect(self.reject);form.addRow(buttons)
        localize_window(self)
        self.setWindowTitle(t(self.windowTitle()))
    def submit(self):
        try:
            if self.first_run:
                if self.password.text()!=self.confirm.text(): raise ValueError(t('Passwords do not match'))
                self.auth.create_admin(self.username.text().strip(),self.password.text())
            elif not self.auth.authenticate(self.username.text().strip(),self.password.text()): raise ValueError(t('Invalid username or password'))
            self.accept()
        except Exception as e: QMessageBox.warning(self, t('Login'), str(e))
