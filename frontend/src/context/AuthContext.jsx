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
    password: '123456',
    role: 'FARM_OWNER',
  },
  {
    id: 2,
    name: 'Technician',
    email: 'tech@nestmate.dev',
    password: '123456',
    role: 'TECHNICIAN',
  },
  {
    id: 3,
    name: 'Administrator',
    email: 'admin@nestmate.dev',
    password: '123456',
    role: 'ADMIN',
  },
]

function AuthProvider({ children }) {
  const [user, setUser] = useState(null)

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

    // Không đưa password vào state.
    const authenticatedUser = {
      id: matchedUser.id,
      name: matchedUser.name,
      email: matchedUser.email,
      role: matchedUser.role,
    }

    setUser(authenticatedUser)

    return {
      success: true,
      user: authenticatedUser,
    }
  }

  const logout = () => {
    setUser(null)
  }

  const value = {
    user,
    login,
    logout,
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