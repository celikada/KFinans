import type { GoalCurrency, GoalDTO } from "./types";
import { request } from "./_client";

export const goalApi = {
  // Finansal hedef
  getGoal: () => request<GoalDTO>("/user/goal"),
  setGoal: (amount: number, currency: GoalCurrency) =>
    request<GoalDTO>("/user/goal", {
      method: "PUT",
      body: JSON.stringify({ amount, currency }),
    }),
};
