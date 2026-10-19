import {
  createContext,
  useContext,
  useState,
} from 'react'

const AuthContext = createContext(null)

/*
 * MOCK DATA
 * Sau này sẽ được thay bằng API Authentication của Backend.
 */
const MOCK_USERS = [
  {
    id: 1,
    name: 'Farm Owner',
    email: 'owner@nestmate.dev',
    phone: '0901 234 567',
    password: '123456',
    role: 'FARM_OWNER',
  },
  {
    id: 2,
    name: 'Technician',
    email: 'tech@nestmate.dev',
    phone: '0902 345 678',
    password: '123456',
    role: 'TECHNICIAN',
  },
  {
    id: 3,
    name: 'Administrator',
    email: 'admin@nestmate.dev',
    phone: '0903 456 789',
    password: '123456',
    role: 'ADMIN',
  },
]

function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const storedUser = localStorage.getItem('nestmate_user')

    if (!storedUser) {
      return null
    }

    try {
      return JSON.parse(storedUser)
    } catch {
      localStorage.removeItem('nestmate_user')
      return null
    }
  })

  const login = (email, password) => {
    const normalizedEmail = email
      .trim()
      .toLowerCase()

    const matchedUser = MOCK_USERS.find(
      (item) =>
        item.email === normalizedEmail &&
        item.password === password,
    )

    if (!matchedUser) {
      return {
        success: false,
        message: 'Email hoặc mật khẩu không chính xác.',
      }
    }

    // Không đưa password vào state/localStorage.
    const authenticatedUser = {
      id: matchedUser.id,
      name: matchedUser.name,
      email: matchedUser.email,
      phone: matchedUser.phone,
      role: matchedUser.role,
    }

    setUser(authenticatedUser)

    localStorage.setItem(
      'nestmate_user',
      JSON.stringify(authenticatedUser),
    )

    return {
      success: true,
      user: authenticatedUser,
    }
  }

  const updateProfile = (profileData) => {
    if (!user) {
      return {
        success: false,
        message: 'Không tìm thấy phiên đăng nhập.',
      }
    }

    const updatedUser = {
      ...user,
      name: profileData.name?.trim() || user.name,
      phone: profileData.phone?.trim() || '',
    }

    setUser(updatedUser)

    localStorage.setItem(
      'nestmate_user',
      JSON.stringify(updatedUser),
    )

    return {
      success: true,
      user: updatedUser,
    }
  }

  const logout = () => {
    setUser(null)
    localStorage.removeItem('nestmate_user')
  }

  const value = {
    user,
    login,
    logout,
    updateProfile,
    isAuthenticated: Boolean(user),
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error(
      'useAuth must be used within AuthProvider',
    )
  }

  return context
}

export {
  AuthProvider,
  useAuth,
}