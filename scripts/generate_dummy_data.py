import csv
import enum
import uuid
import os
from datetime import datetime, timedelta
import random
import json
import traceback
from faker import Faker
from faker.providers import address, person, phone_number, lorem

print("Script started successfully")

# Initialize Faker
fake = Faker()
Faker.seed(42)  # For reproducible results

# Add custom providers
class MeterProvider:
    def __init__(self, generator):
        self.generator = generator
    
    def meter_manufacturer(self):
        return random.choice(['Siemens', 'Honeywell', 'Schneider', 'Landis+Gyr', 'Itron'])
        
    def meter_model(self, meter_type):
        prefix = 'DIG' if meter_type == MeterType.DIGITAL else 'ANL'
        return f"{prefix}-{random.randint(1000, 9999)}"

fake.add_provider(MeterProvider)  # Pass the class

# Configurable constants (can be overridden via environment variables)
NUM_USERS = int(os.getenv('NUM_USERS', 10))
NUM_METERS = int(os.getenv('NUM_METERS', 100))
NUM_READINGS = int(os.getenv('NUM_READINGS', 500))
NUM_ASSIGNMENTS = int(os.getenv('NUM_ASSIGNMENTS', 50))
NUM_APPROVALS = int(os.getenv('NUM_APPROVALS', 30))
NUM_REGIONS = int(os.getenv('NUM_REGIONS', 5))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 100))  # For incremental CSV writing

# Enums from models
class UserRole:
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"

class UserStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class MeterType(str, enum.Enum):
    DIGITAL = "digital"
    ANALOG = "analog"

class MeterPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class MeterStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    OUT_OF_SERVICE = "out_of_service"

class AssignmentStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class ApprovalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class RegionStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"

# Helper function for coordinate generation
def generate_coordinates(region, lat_range=0.1, lng_range=0.1):
    lat, lng = map(float, region['coordinates'].replace('SRID=4326;POINT(', '').replace(')', '').split())
    lat += random.uniform(-lat_range, lat_range)
    lng += random.uniform(-lng_range, lng_range)
    return f"SRID=4326;POINT({lng} {lat})"

# Generate Regions
def generate_regions():
    cities = ['Malabo', 'Bata', 'Ebebiyin', 'Mongomo', 'Luba', 'Aconibe', 'Evinayong']
    regions = []
    for i in range(NUM_REGIONS):
        # Use city name if available, otherwise generate generic name
        name = cities[i] if i < len(cities) else f"Region_{i + 1}"
        region = {
            'id': str(uuid.uuid4()),
            'name': name,
            'description': f"City {i + 1} in Equatorial Guinea",
            'coordinates': f"SRID=4326;POINT({8.5 + i * 0.5} {3.5 + i * 0.5})",
            'radius': random.uniform(3000, 8000),
            'agent_count': random.randint(3, 10),
            'meter_count': random.randint(20, 50),
            'status': RegionStatus.ACTIVE,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'updated_at': datetime.utcnow().isoformat() + 'Z'
        }
        regions.append(region)
    return regions

# Generate Users
def generate_users(regions):
    users = []
    roles = [UserRole.ADMIN] * 2 + [UserRole.MANAGER] * 3 + [UserRole.AGENT] * (NUM_USERS - 5)
    
    for i in range(1, NUM_USERS + 1):
        role = roles[i - 1] if i <= len(roles) else UserRole.AGENT
        user_status = random.choice([UserStatus.ACTIVE, UserStatus.INACTIVE, UserStatus.SUSPENDED])
        region = random.choice(regions) if role == UserRole.AGENT else None
        
        if role == UserRole.AGENT and not region:
            raise ValueError(f"Agent user{i} must be assigned to a region")
        
        permissions = (
            ['read', 'write', 'manage_users'] if role == UserRole.ADMIN else
            ['read', 'write'] if role == UserRole.MANAGER else
            ['read']
        )
        
        user = {
            'id': str(uuid.uuid4()),
            'email': f"{role}{i}@example.com".lower(),
            'password_hash': f"$2b$12${fake.sha256()[:40]}",
            'name': fake.name(),
            'role': role,
            'status': user_status,
            'phone': f"+240{random.randint(200000000, 299999999)}",
            'department': 'Administration' if role == UserRole.ADMIN else 'Operations' if role == UserRole.MANAGER else 'Field',
            'region': region['name'] if region else None,
            'permissions': permissions,
            'created_at': (datetime.utcnow() - timedelta(days=random.randint(30, 365))).isoformat() + 'Z',
            'updated_at': (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat() + 'Z',
            'last_login': (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat() + 'Z' if random.random() > 0.2 else None
        }
        users.append(user)
    return users

# Generate Meters
def generate_meters(regions):
    meters = []
    meter_types = list(MeterType)
    
    for i in range(1, NUM_METERS + 1):
        meter_type = random.choices(meter_types, weights=[0.7, 0.3])[0]
        region = random.choice(regions)
        manufacturer = fake.meter_manufacturer()
        model = fake.meter_model(meter_type)
        
        meter = {
            'id': str(uuid.uuid4()),
            'serial_number': f"MTR-{i:06d}",
            'address': f"{random.randint(1, 1000)} {fake.street_name()}",
            'location_id': region['id'],
            'meter_type': meter_type,
            'priority': random.choices(
                [MeterPriority.LOW, MeterPriority.MEDIUM, MeterPriority.HIGH, MeterPriority.CRITICAL],
                weights=[0.5, 0.3, 0.15, 0.05]
            )[0],
            'status': random.choices(
                [MeterStatus.ACTIVE, MeterStatus.INACTIVE, MeterStatus.MAINTENANCE, MeterStatus.OUT_OF_SERVICE],
                weights=[0.8, 0.1, 0.08, 0.02]
            )[0],
            'last_reading': None,
            'estimated_time': random.choice([15, 30, 45, 60]),
            'coordinates': generate_coordinates(region),
            'owner': fake.company(),
            'meter_metadata': {
                'manufacturer': manufacturer,
                'model': model,
                'meter_type': meter_type,
                'voltage': random.choice(['110V', '220V', '380V']),
                'max_current': random.choice(['60A', '100A', '200A']),
                'accuracy_class': '0.5S' if meter_type == MeterType.DIGITAL else '1.0',
                'installation_date': (datetime.utcnow() - timedelta(days=random.randint(1, 1000))).strftime('%Y-%m-%d'),
                'last_calibration': (datetime.utcnow() - timedelta(days=random.randint(30, 365))).strftime('%Y-%m-%d') if random.random() > 0.2 else None,
                'installation_notes': fake.sentence() if random.random() > 0.7 else None
            },
            'created_at': (datetime.utcnow() - timedelta(days=random.randint(1, 1000))).isoformat() + 'Z',
            'updated_at': (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat() + 'Z'
        }
        meters.append(meter)
    return meters

# Generate Readings
def generate_readings(users, meters):
    readings = []
    agents = [u for u in users if u['role'] == UserRole.AGENT]
    
    for i in range(1, NUM_READINGS + 1):
        meter = random.choice(meters)
        agent = random.choice(agents)
        reading_date = datetime.utcnow() - timedelta(days=random.randint(0, 30))
        
        # Get meter coordinates
        coords = meter['coordinates'].replace('SRID=4326;POINT(', '').replace(')', '').split()
        lng, lat = map(float, coords)
        
        reading = {
            'id': str(uuid.uuid4()),
            'meter_id': meter['id'],
            'agent_id': agent['id'],
            'reading_value': round(random.uniform(100, 10000), 2),
            'reading_timestamp': reading_date.isoformat() + 'Z',
            'photo_url': f"https://picsum.photos/200/300?image={i}" if random.random() > 0.7 else None,
            'notes': fake.sentence() if random.random() > 0.7 else None,
            'location': f"SRID=4326;POINT({lng + random.uniform(-0.001, 0.001)} {lat + random.uniform(-0.001, 0.001)})",
            'verified': random.choices([True, False], weights=[0.8, 0.2])[0],
            'created_at': (reading_date + timedelta(minutes=random.randint(1, 60))).isoformat() + 'Z'
        }
        readings.append(reading)
    
    # Update last_reading for each meter based on the most recent reading
    for meter in meters:
        meter_readings = [r for r in readings if r['meter_id'] == meter['id']]
        if meter_readings:
            latest_reading = max(meter_readings, key=lambda x: x['reading_timestamp'])
            meter['last_reading'] = latest_reading['reading_value']
            meter['updated_at'] = latest_reading['created_at']
    
    return readings

# Generate Assignments
def generate_assignments(users, meters):
    assignments = []
    agents = [u for u in users if u['role'] == UserRole.AGENT]
    
    for i in range(1, NUM_ASSIGNMENTS + 1):
        meter = random.choice(meters)
        agent = random.choice(agents)
        assigned_date = datetime.utcnow() - timedelta(days=random.randint(1, 90))
        
        status = random.choices(
            [AssignmentStatus.PENDING, AssignmentStatus.IN_PROGRESS, AssignmentStatus.COMPLETED, 
             AssignmentStatus.CANCELLED, AssignmentStatus.OVERDUE],
            weights=[0.2, 0.3, 0.4, 0.05, 0.05]
        )[0]
        
        if status == AssignmentStatus.COMPLETED:
            completed_date = assigned_date + timedelta(hours=random.randint(1, 72))
            completion_notes = fake.sentence() if random.random() > 0.5 else None
        elif status == AssignmentStatus.CANCELLED:
            completed_date = assigned_date + timedelta(hours=random.randint(1, 24))
            completion_notes = "Assignment cancelled: " + fake.sentence()
        else:
            completed_date = None
            completion_notes = None
        
        assignment = {
            'id': str(uuid.uuid4()),
            'meter_id': meter['id'],
            'agent_id': agent['id'],
            'status': status,
            'estimated_time': random.choice([15, 30, 45, 60, 90, 120]),
            'assigned_at': assigned_date.isoformat() + 'Z',
            'completed_at': completed_date.isoformat() + 'Z' if completed_date else None,
            'completion_notes': completion_notes,
            'created_at': assigned_date.isoformat() + 'Z',
            'updated_at': (completed_date if completed_date else assigned_date).isoformat() + 'Z'
        }
        assignments.append(assignment)
    return assignments

# Generate Approvals
def generate_approvals(users, meters):
    approvals = []
    agents = [u for u in users if u['role'] == UserRole.AGENT]
    reviewers = [u for u in users if u['role'] in [UserRole.ADMIN, UserRole.MANAGER]]
    
    for i in range(1, NUM_APPROVALS + 1):
        meter = random.choice(meters)
        agent = random.choice(agents)
        submitted_date = datetime.utcnow() - timedelta(days=random.randint(1, 30))
        
        status = random.choices(
            [ApprovalStatus.PENDING, ApprovalStatus.APPROVED, ApprovalStatus.REJECTED],
            weights=[0.3, 0.5, 0.2]
        )[0]
        
        if status != ApprovalStatus.PENDING:
            reviewed_date = submitted_date + timedelta(hours=random.randint(1, 72))
            reviewed_by = random.choice(reviewers)['id']
            review_notes = fake.sentence()
        else:
            reviewed_date = None
            reviewed_by = None
            review_notes = None
        
        request_type = random.choice(['replacement', 'maintenance', 'inspection', 'calibration'])
        
        approval = {
            'id': str(uuid.uuid4()),
            'meter_id': meter['id'],
            'agent_id': agent['id'],
            'status': status,
            'request_type': request_type,
            'submission_notes': f"Request for {request_type}: {fake.sentence()}",
            'reviewed_at': reviewed_date.isoformat() + 'Z' if reviewed_date else None,
            'reviewed_by': reviewed_by,
            'review_notes': review_notes,
            'created_at': submitted_date.isoformat() + 'Z',
            'updated_at': (reviewed_date if reviewed_date else submitted_date).isoformat() + 'Z'
        }
        approvals.append(approval)
    return approvals

# Handle special types like dicts and lists by converting them to JSON strings
def clean_value(value):
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            print(f"Error serializing value {value}: {str(e)}")
            return str(value)
    return value

# Save data to CSV with batch processing
def save_to_csv(data, filename, fieldnames=None):
    if not fieldnames and data:
        fieldnames = list(data[0].keys())
    
    try:
        os.makedirs('dummy_data', exist_ok=True)
        with open(f'dummy_data/{filename}.csv', 'w', newline='', encoding='utf-8') as f:
            f.write(f"# Generated by generate_dummy_data.py on {datetime.utcnow().isoformat()}Z\n")
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for i in range(0, len(data), BATCH_SIZE):
                batch = data[i:i + BATCH_SIZE]
                for row in batch:
                    cleaned_row = {k: clean_value(v) for k, v in row.items() if k in fieldnames}
                    writer.writerow(cleaned_row)
    except IOError as e:
        print(f"Error writing to {filename}.csv: {str(e)}")
        raise

def main():
    try:
        print("Starting script...")
        print("Creating output directory...")
        os.makedirs('dummy_data', exist_ok=True)
        
        print("Generating regions...")
        regions = generate_regions()
        
        print("Generating users...")
        users = generate_users(regions)
        
        print("Generating meters...")
        meters = generate_meters(regions)
        
        print("Generating readings...")
        readings = generate_readings(users, meters)
        
        print("Generating assignments...")
        assignments = generate_assignments(users, meters)
        
        print("Generating approvals...")
        approvals = generate_approvals(users, meters)
        
        print("Saving data to CSV files...")
        save_to_csv(regions, 'regions')
        save_to_csv(users, 'users', ['id', 'email', 'name', 'role', 'status', 'phone', 'department', 'region', 'permissions', 'created_at', 'updated_at', 'last_login'])
        save_to_csv(meters, 'meters', ['id', 'serial_number', 'address', 'location_id', 'meter_type', 'priority', 'status', 'last_reading', 'estimated_time', 'coordinates', 'owner', 'meter_metadata', 'created_at', 'updated_at'])
        save_to_csv(readings, 'meter_readings')
        save_to_csv(assignments, 'meter_assignments')
        save_to_csv(approvals, 'meter_approvals')
        
        print("\nDummy data generation completed successfully!")
        print(f"Generated files in {os.path.abspath('dummy_data')}:")
        for f in os.listdir('dummy_data'):
            if f.endswith('.csv'):
                print(f"- {f}")
                
    except Exception as e:
        print(f"\nError generating dummy data: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()