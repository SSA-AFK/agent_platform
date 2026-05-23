import request from '@/utils/request'

export interface UserInfo {
  id: number
  username: string
  nickname?: string
  avatar?: string
  gender?: string
  bio?: string
}

export interface UserUpdateRequest {
  nickname?: string
  avatar?: string
  gender?: string
  bio?: string
  phone?: string
}

export interface UserChangePasswordRequest {
  oldPassword: string
  newPassword: string
}

export const getUserInfo = () => {
  return request.get<UserInfo>('/api/user/info')
}

export const updateUser = (data: UserUpdateRequest) => {
  return request.put<UserInfo>('/api/user/update', data)
}

export const changePassword = (data: UserChangePasswordRequest) => {
  return request.put('/api/user/password', data)
}
