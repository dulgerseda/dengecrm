import matplotlib.pyplot as plt
import streamlit as st
import pandas as pd
import datetime as dt

df = pd.read_excel(r"V2.xlsx", sheet_name="Sayfa1")

df = df.groupby('Fatura').agg({
    'Cari': 'first',  # Her grup için ilk CustomerID değerini al
    'Ad': 'first',
    'Tarih': 'first',  # Her grup için ilk InvoiceDate değerini al
    'Urun': lambda x: list(x),  # Alınan ürünlerin listesi
    'Kg': 'sum',  # Her fatura için Kg değerlerinin toplamı
    'Tutar': 'sum'  # Her fatura için Value değerlerinin toplamı
}).reset_index()

df.head()

today_date = dt.datetime(2024, 3, 10)
df['Cari'] = df['Cari'].astype(str)
df['Ad'] = df['Ad'].astype(str)


##############   RFM  ##########


def create_rfm(df, csv=False):
    # VERIYI HAZIRLAMA
    today_date = dt.datetime(2024, 3, 10)
    rfm = df.groupby('Cari').agg({
        'Tarih': lambda x: (today_date - x.max()).days,
        'Cari': lambda x: x.nunique(),
        'Tutar': lambda x: x.sum()
    })
    rfm.columns = ['recency', 'frequency', 'monetary']

    # RFM METRIKLERININ HESAPLANMASI
    rfm["recency_score"] = pd.qcut(rfm['recency'], 5, labels=[5, 4, 3, 2, 1])
    rfm["frequency_score"] = pd.qcut(rfm['frequency'].rank(method="first"), 5, labels=[1, 2, 3, 4, 5])
    rfm["monetary_score"] = pd.qcut(rfm['monetary'], 5, labels=[1, 2, 3, 4, 5])

    # RFM SKORLARININ BIRLESTIRILMESI
    rfm["RFM_SCORE"] = rfm['recency_score'].astype(str) + rfm['frequency_score'].astype(str)

    # SEGMENTLERIN ISIMLENDIRILMESI
    seg_map = {
        r'[1-2][1-2]': 'hibernating',
        r'[1-2][3-4]': 'at_risk',
        r'[1-2]5': 'cant_loose',
        r'3[1-2]': 'about_to_sleep',
        r'33': 'need_attention',
        r'[3-4][4-5]': 'loyal_customers',
        r'41': 'promising',
        r'51': 'new_customers',
        r'[4-5][2-3]': 'potential_loyalists',
        r'5[4-5]': 'champions'
    }
    rfm['segment'] = rfm['RFM_SCORE'].replace(seg_map, regex=True)

    if csv:
        rfm.to_csv("rfm.csv")

    return rfm


rfm_new = create_rfm(df, csv=False)
rfm_new.head()


#########  CLTV  ##############

def create_cltv_denge(dataframe, profit=0.10):
    # Veriyi hazırlama
    cltv_c = dataframe.groupby('Cari').agg({'Fatura': lambda x: x.nunique(),
                                            'Kg': lambda x: x.sum(),
                                            'Tutar': lambda x: x.sum()})
    cltv_c.columns = ['total_transaction', 'total_unit', 'Value']
    # avg_order_value
    cltv_c['avg_order_value'] = cltv_c['Value'] / cltv_c['total_transaction']
    # purchase_frequency
    cltv_c["purchase_frequency"] = cltv_c['total_transaction'] / cltv_c.shape[0]
    # cltv_c.shape[0] kaç satır oldupunu gösterir
    # repeat rate & churn rate
    repeat_rate = cltv_c[cltv_c.total_transaction > 1].shape[0] / cltv_c.shape[0]
    # tekrar eden müşteri sayısının toplam müşteri sayısına oranını hesaplar
    churn_rate = 1 - repeat_rate
    # profit_margin
    cltv_c['profit_margin'] = cltv_c['Value'] * profit
    # Customer Value
    cltv_c['customer_value'] = (cltv_c['avg_order_value'] * cltv_c["purchase_frequency"])
    # Customer Lifetime Value
    cltv_c['cltv'] = (cltv_c['customer_value'] / churn_rate) * cltv_c['profit_margin']
    # Segment
    cltv_c["segment_clv_now"] = pd.qcut(cltv_c["cltv"], 4, labels=["D", "C", "B", "A"])

    return cltv_c


clv_now = create_cltv_denge(df)
clv_now.head()

customer_names = df[['Cari', 'Ad']].drop_duplicates()
rfm_with_names = pd.merge(rfm_new, customer_names, on='Cari', how='left')
rfm_with_names.head(5)
clv_with_names = pd.merge(clv_now, customer_names, on='Cari', how='left')
clv_with_names.head(5)

df['Tarih'] = pd.to_datetime(df['Tarih'])


def get_monthly_purchases(customer_name, year):
    filtered_df = df[(df['Ad'] == customer_name) & (df['Tarih'].dt.year == year)]
    monthly_purchases = filtered_df.groupby(filtered_df['Tarih'].dt.month).size()
    # Eğer bazı aylarda satın alma yoksa, o aylar için 0 değeriyle doldurma
    all_months = pd.Series([0] * 12, index=range(1, 13))
    all_months.update(monthly_purchases)
    plt.figure(figsize=(10, 5))
    all_months.plot(kind='line', marker='o', linestyle='-')
    plt.title(f'Aylık Satın Alma Sayısı - {customer_name} ({year})')
    plt.xlabel('Ay')
    plt.ylabel('Satın Alma Sayısı')
    plt.grid(True)
    plt.xticks(range(1, 13))
    plt.show(block=True)
    return all_months


a1, a2, a3, a4 = st.columns(4)
a1.image("denge.png", width=200)


# Ana fonksiyon
def main():
    # Sekmeleri oluştur
    tab1, tab2, tab3 = st.tabs(["CRM Segmentasyonu", "Yıllık Satış", "Ürün Önerisi"])

    with tab1:
        customerNamePart = st.text_input('Müşteri Adını Giriniz:')

        # "Sınıfı Gör" butonu
        if st.button('Sınıfı Gör'):
            # Müşteri adı parçasının veri çerçevelerindeki adlar içinde olup olmadığını kontrol edin
            matching_customers_rfm = rfm_with_names[
                rfm_with_names['Ad'].str.contains(customerNamePart, case=False, na=False)]
            matching_customers_clv = clv_with_names[
                clv_with_names['Ad'].str.contains(customerNamePart, case=False, na=False)]

            if not matching_customers_rfm.empty:
                for index, row in matching_customers_rfm.iterrows():
                    # CLV segmentini bulun
                    clv_segment = matching_customers_clv[matching_customers_clv['Ad'] == row['Ad']][
                        "segment_clv_now"].iloc[0]
                    # Sonuçları göster
                    st.write(
                        f'Müşteri {row["Ad"]} için RFM (satın alma sayısı ve sıklığına göre) sınıfı: {row["segment"]}')
                    st.write(f'Müşteri {row["Ad"]} için CLV (Bıraktığı değere göre) sınıfı: {clv_segment}')
            else:
                # Eşleşen müşteri bulunamazsa uyarı göster
                st.write("Bu isimle eşleşen bir müşteri bulunamadı.")

    with tab2:
        st.title('Müşteri Aylık Satın Alma İstatistikleri')
        df = pd.read_excel(r"V2.xlsx", sheet_name="Sayfa1")
        df = df.groupby('Fatura').agg({
            'Cari': 'first',  # Her grup için ilk CustomerID değerini al
            'Ad': 'first',
            'Tarih': 'first',  # Her grup için ilk InvoiceDate değerini al
            'Urun': lambda x: list(x),  # Alınan ürünlerin listesi
            'Kg': 'sum',  # Her fatura için Kg değerlerinin toplamı
            'Tutar': 'sum'  # Her fatura için Value değerlerinin toplamı
        }).reset_index()
        df['Tarih'] = pd.to_datetime(df['Tarih'])
        # Kullanıcıdan giriş alın
        customer_name = st.selectbox('Müşteri Seçiniz', df['Ad'].unique())
        year = st.selectbox('Yıl Seçiniz', df['Tarih'].dt.year.unique())
        # Sonuçları çizdir
        monthly_purchases = get_monthly_purchases(customer_name, year)
        # Çizgi grafiği çiz
        fig, ax = plt.subplots()
        ax.plot(monthly_purchases.index, monthly_purchases.values, marker='o', linestyle='-', color='b')
        ax.set_title(f'Aylık Satın Alma Sayısı - {customer_name} ({year})')
        ax.set_xlabel('Ay')
        ax.set_ylabel('Satın Alma Sayısı')
        ax.grid(True)
        ax.set_xticks(range(1, 13))

        # Streamlit'e grafik çizimi yap
        st.pyplot(fig)

    with tab3:
        st.title('Ürün Öneri Sistemi')
        # Excel dosyasını okuma ve DataFrame oluşturma
        df = pd.read_excel(r"V2.xlsx", sheet_name="LABONERI")
        # DataFrame'i gruplayarak önerilen ürün adlarını ve kodlarını listeleme
        grouped_df = df.groupby('UrunAdi').agg({
            'OnerilenUrunAdi': lambda x: list(x),
            # 'OnerilenUrunKodu': lambda x: list(x)  # Önerilen ürün kodlarını da dahil et
        }).reset_index()

        # Gruplanmış DataFrame'i kullanmak üzere ayarlama
        df = grouped_df

        # Kullanıcıdan ürün adı girişi alma
        user_input = st.text_input("Rakip Ürün adı girin:")

        # Kullanıcı giriş yaptığında işlemleri gerçekleştirme
        if user_input:
            # Giriş yapılan ürün adı ile eşleşen önerileri filtreleme
            filtered_df = df[df['UrunAdi'].str.contains(user_input, case=False, na=False)]

            if not filtered_df.empty:
                st.write("Önerilen Ürünler ve Kodları:")
                # Önerilen ürünleri ve kodlarını gösterme
                for index, row in filtered_df.iterrows():
                    st.write(f"{row['OnerilenUrunAdi']}")
                    # st.write(f"{row['OnerilenUrunAdi']} # - {row['OnerilenUrunKodu']}")
            else:
                st.write("Bu ürün adıyla ilgili bir öneri bulunamadı.")
                st.title('Ürün Öneri Sistemi')

                st.write("Tam DataFrame:")
                st.dataframe(df)
        df_onerı = pd.read_excel(r"V2.xlsx", sheet_name="LABONERI")
        st.write("Tam DataFrame:")
        st.dataframe(df_onerı)


if __name__ == "__main__":
    main()

# streamlit run denge_crm_tum_str.py
# RSE CONZ
