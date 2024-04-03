"use server"
import { cookies } from "next/headers";

export const getUser = async () =>{
    const isCookies = cookies().get("access_token")?.value;
    try {
        const res = await fetch(`http://localhost:3000//api/users/me`, {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${isCookies}`
            },
        })
        const data = await res.json()      
        return data
    }
    catch (error) {
        console.log(error, "error");
        console.log("error is error");
    }
}