import { createMongoAbility } from '@casl/ability'

export type Actions = 'create' | 'read' | 'update' | 'delete' | 'manage'

// ex: Post, Comment, User, etc. We haven't used any of these in our demo though.
export type Subjects = 'Post' | 'Comment' | 'all'

export interface Rule { action: Actions; subject: string; inverted?: boolean }

export const ability = createMongoAbility<[Actions, Subjects]>()
