package com.example.pic_ai_app.masking.regex

internal object NumberPatterns {

    val phoneNumber: Regex = Regex(
    """(?<![0-9])(?<![0-9][-\.])""" +

            """(?:""" +

            // 010 휴대전화와 070 인터넷전화
            """(?:010|070)[- .\t]?[0-9]{4}[- .\t]?[0-9]{4}""" +

            // 서울 및 나머지 지역번호
            """|(?:02|03[1-3]|04[1-4]|05[1-5]|06[1-4])[- .\t]?[0-9]{3,4}[- .\t]?[0-9]{4}""" +

            // 뒤에 다른 숫자나 '-숫자'/ '.숫자'가 이어지지 않아야 한다.
            """)(?![0-9]|[-.][0-9])"""
    )

    val RRn : Regex = Regex()

    val cardNumber : Regex = Regex()

    val accountNumber : Regex = Regex()

    val birth : Regex = Regex()

}

