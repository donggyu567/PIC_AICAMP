package com.example.pic_ai_app.masking.model

enum class MaskType {
    PERSON,         //이름
    ADDRESS,        //주소
    PHONE_NUMBER,   //전화번호
    RRN,            //주민번호
    CARD_NUMBER,    //카드번호
    ACCOUNT_NUMBER, //계좌번호
    BIRTH,          //생년월일
    EMAIL,          //이메일 주소
    PW,             //비밀번호
    MASKED          //유형을 확정할 수 없지만 보호해야 하는 값
}





