import { isEmpty, isEmptyArray, isNullOrUndefined } from './helpers'

// 👉 Required Validator
export const requiredValidator = (value: unknown) => {
  if (isNullOrUndefined(value) || isEmptyArray(value) || value === false)
    return 'This field is required'

  return !!String(value).trim().length || 'This field is required'
}

// 👉 Email Validator
export const emailValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  const re = /^(?:[^<>()[\]\\.,;:\s@"]+(?:\.[^<>()[\]\\.,;:\s@"]+)*|".+")@(?:\[\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\]|(?:[a-z\-\d]+\.)+[a-z]{2,})$/i

  if (Array.isArray(value))
    return value.every(val => re.test(String(val))) || 'The Email field must be a valid email'

  return re.test(String(value)) || 'The Email field must be a valid email'
}

/**
 * Matches attendance API `_flex_email` (allows internal domains such as `@juku.local`).
 * Pair with {@link requiredValidator} when the address is mandatory.
 */
export const internalEmailValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  const normalized = String(value).trim()
  if (normalized.length < 3 || normalized.length > 255)
    return 'Email must be 3–255 characters'

  const at = normalized.indexOf('@')
  if (at <= 0 || at !== normalized.lastIndexOf('@'))
    return 'Enter a valid email (use exactly one @)'

  const localPart = normalized.slice(0, at)
  const domainPart = normalized.slice(at + 1)
  if (!localPart || !domainPart)
    return 'Enter a valid email'

  if (Array.from(localPart).some(c => /\s/.test(c)) || Array.from(domainPart).some(c => /\s/.test(c)))
    return 'Email must not contain spaces'

  return true
}

/** Attendance user create – API requires 6–128 characters. Use after {@link requiredValidator}. */
export const attendanceCreatePasswordValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  const s = String(value)
  if (s.length < 6)
    return 'Password must be at least 6 characters'

  if (s.length > 128)
    return 'Password must be at most 128 characters'

  return true
}

/** Username / code for attendance users – max 100 after trim; use with {@link requiredValidator}. */
export const usernameAttendanceValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  const trimmed = String(value).trim()
  if (!trimmed.length)
    return 'Username cannot be only spaces'

  if (trimmed.length > 100)
    return 'Username must be at most 100 characters'

  return true
}

/** Optional field max length (empty values pass). */
export const maxCharsRule = (max: number, label = 'This field') => {
  return (value: unknown) => {
    if (isEmpty(value))
      return true

    return String(value).length <= max || `${label} must be at most ${max} characters`
  }
}

// 👉 Password Validator
export const passwordValidator = (password: string) => {
  const regExp = /(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%&*()]).{8,}/

  const validPassword = regExp.test(password)

  return validPassword || 'Field must contain at least one uppercase, lowercase, special character and digit with min 8 chars'
}

// 👉 Confirm Password Validator
export const confirmedValidator = (value: string, target: string) =>

  value === target || 'The Confirm Password field confirmation does not match'

// 👉 Between Validator
export const betweenValidator = (value: unknown, min: number, max: number) => {
  const valueAsNumber = Number(value)

  return (Number(min) <= valueAsNumber && Number(max) >= valueAsNumber) || `Enter number between ${min} and ${max}`
}

// 👉 Integer Validator
export const integerValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  if (Array.isArray(value))
    return value.every(val => /^-?\d+$/.test(String(val))) || 'This field must be an integer'

  return /^-?\d+$/.test(String(value)) || 'This field must be an integer'
}

// 👉 Regex Validator
export const regexValidator = (value: unknown, regex: RegExp | string): string | boolean => {
  if (isEmpty(value))
    return true

  let regeX = regex
  if (typeof regeX === 'string')
    regeX = new RegExp(regeX)

  if (Array.isArray(value))
    return value.every(val => regexValidator(val, regeX))

  return regeX.test(String(value)) || 'The Regex field format is invalid'
}

// 👉 Alpha Validator
export const alphaValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  return /^[A-Z]*$/i.test(String(value)) || 'The Alpha field may only contain alphabetic characters'
}

// 👉 URL Validator
export const urlValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  const re = /^https?:\/\/[^\s$.?#].\S*$/

  return re.test(String(value)) || 'URL is invalid'
}

// 👉 Length Validator
export const lengthValidator = (value: unknown, length: number) => {
  if (isEmpty(value))
    return true

  return String(value).length === length || `The Min Character field must be at least ${length} characters`
}

// 👉 Alpha-dash Validator
export const alphaDashValidator = (value: unknown) => {
  if (isEmpty(value))
    return true

  const valueAsString = String(value)

  return /^[\w-]*$/.test(valueAsString) || 'All Character are not valid'
}
