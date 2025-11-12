import { EventEmitter } from "eventemitter3";

export const tokenEmitter = new EventEmitter();
export const TOKEN_CHANGED = "token_changed";
