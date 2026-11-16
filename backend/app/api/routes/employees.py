from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.models import Employee, User
from app.schemas.schemas import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.api.dependencies.auth import get_current_user, require_role
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/employees", tags=["Employees"])

@router.get("", response_model=List[EmployeeResponse])
def list_employees(
    department: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List office employees with department and search filters."""
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    if search:
        term = f"%{search}%"
        query = query.filter((Employee.full_name.ilike(term)) | (Employee.employee_code.ilike(term)) | (Employee.email.ilike(term)))
    return query.order_by(Employee.full_name).all()

@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    emp_in: EmployeeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    """Register new office employee (Admin only)."""
    existing = db.query(Employee).filter(
        (Employee.email == emp_in.email) | (Employee.employee_code == emp_in.employee_code)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this code or email already exists.")

    emp = Employee(**emp_in.dict())
    db.add(emp)
    db.commit()
    db.refresh(emp)

    log_audit_event(
        db=db,
        entity_type="EMPLOYEE",
        entity_id=emp.id,
        action="CREATE",
        actor_user_id=admin.id,
        new_values=emp_in.dict()
    )
    return emp

@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: str,
    emp_update: EmployeeUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    old_data = {"full_name": emp.full_name, "email": emp.email, "department": emp.department, "is_active": emp.is_active}
    update_data = emp_update.dict(exclude_unset=True)
    for field, val in update_data.items():
        setattr(emp, field, val)

    db.commit()
    db.refresh(emp)

    log_audit_event(
        db=db,
        entity_type="EMPLOYEE",
        entity_id=emp.id,
        action="UPDATE",
        actor_user_id=admin.id,
        old_values=old_data,
        new_values=update_data
    )
    return emp

@router.delete("/{employee_id}", status_code=status.HTTP_200_OK)
def delete_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["ADMIN"]))
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Soft delete / deactivation
    emp.is_active = False
    db.commit()

    log_audit_event(
        db=db,
        entity_type="EMPLOYEE",
        entity_id=emp.id,
        action="DEACTIVATE",
        actor_user_id=admin.id
    )
    return {"message": f"Employee {emp.full_name} deactivated."}
