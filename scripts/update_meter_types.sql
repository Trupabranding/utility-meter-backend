-- Drop existing constraints that depend on the meter_type enum
ALTER TABLE meters DROP CONSTRAINT IF EXISTS meters_meter_type_check;

-- Create a new enum type with the correct values
CREATE TYPE meter_type_new AS ENUM ('digital', 'analog');

-- Alter the table to use the new enum type
ALTER TABLE meters 
    ALTER COLUMN meter_type TYPE VARCHAR,
    ALTER COLUMN meter_type DROP DEFAULT;

-- Drop the old enum type
DROP TYPE meter_type;

-- Rename the new enum type to the original name
ALTER TYPE meter_type_new RENAME TO meter_type;

-- Update the column to use the new enum type
ALTER TABLE meters 
    ALTER COLUMN meter_type TYPE meter_type 
    USING meter_type::meter_type,
    ALTER COLUMN meter_type SET NOT NULL;
