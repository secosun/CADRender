/**
 * Download Yili color card images from WeChat article, organized by series.
 *
 * Article: 2022年蚁力色卡大全
 * URL: https://mp.weixin.qq.com/s/WIe1DYH4TYNb3irvroHuyA
 */
const fs = require("fs");
const https = require("https");
const path = require("path");

const BASE_DIR = "D:/咸阳/框架评审/CADRender/outputs/蚁力色卡";

// Image groups by series (extracted from article structure)
const SERIES = {
  "01-户外砂纹系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwoDp5JMcibvJoWDT59Uu7dKiaEzh3GjsyuFoe9xCtURRhWHypvAeBqkNg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwBOguKYIhicwOicl0g0t98adL7Gl7CSz3PewJM7M7RCA7ib1zcNx26wZVg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwvsiaapbwznpTCCDRHp32XcCfj5q6eG5Bam793nxp42Z0pT9jOUrydvQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwMYcZMOtNeso8DFl8hKTlEWCTx3YiaXwbqw7q8bReHE59Yz9JF2A55Hg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwnazepBxgvrfrlVpH5aqKgzZmBOvyj2auHU7pCaznWXlaHQUPYaP8WQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwqZiacZSV2ZdhSsSyrSRV5iaiaXrib3Sicc2CvFFhk04ycOQX4M4DVI6PeJg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEmKibWceXslf09gJWk7DoSqKPc086l8m8rB65fDKEShic7WFevZ8qjBpA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEgxP2OEbR8wQibBfibhGKHQialib7Oiapy1BSk4lE2HFCYpz8pjicJTFtKVzA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEy47MBl3tJUniaBlGc4uPDIvIdXxLqYrpgDLvMQgkgOyHoTpBaWiaiadZQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9vDKIXeSZfWt6ukBzIpmfdo83b9clsrUsmj9uUSMTVStHk8iblzZ6g0w/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9GeCiagJpb75VJAb8yl0A92mMgm3bVnia7Fn5IIC9eDibbMFIs7D2speFw/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9hXHR3wlN8D7H2TbrMicPsf3cP4xHxtJ6zQyxxYFsURK2NZcub2aXXEg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9d2rzttpxJO9CDDtV2dKQCO4KZ53UsiagMYLnXhFgiacOkwfk4YSxNj0w/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9iaZwmyngickszu9q893g01xyA3SnFAwMlPcibaDmaMicXGVI0omf1S2tEg/640?wx_fmt=jpeg",
  ],
  "02-户外微晶陶瓷系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZT9GhvJKKeeCoDW64cCTxSCKFsrxfBWOSEoKl3uAdZBOKeX7ZMQpgLuQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTLLFiadbEhdAfHLgVYqSxtV9RjamibLwUyLIt4naztYt04827uXQjAZfg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTgI5ibpBJ3lr9XJ7tEDdDSbibO6eoicbfsdVan8GiaiayMfd1Gbf1IFFacMg/640?wx_fmt=jpeg",
  ],
  "03-户外超耐候系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG94MqmEMOzEMHFbhE3OMAY3kWqbAfHJbcEibXQsR6qDVB6GVcdXasqrKg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9mIK5jeiarCZ9xRYgbWZ1Ij2lZ8fweNWmazIeQXn0uibNk11ReETOscxg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9ibWehsibh1iadYGBKbkPfOTicKHWIhPe4MXxeb8wNN1qJ5wE1z5N57twlA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9vhB4mM9sfKiaMzicmz1EPiaIozm3icadEEptEB9sTp9LicibiaHnpIXkMCnNw/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTH1XYfP45GfkIPMuiaPL2okia3QVYtZ10kcl1yHSDzWFKZUiaUKXn1O1dA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9DniaeHacYvyxSe2yn1zOGs38cpOicP78dd4Wbgxx7O93PvqEBmzRos1g/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9Jyz8wtQRhzLpRNTs4RpH2CoDpetCufEiaibU2A44nwsYYN0rWQCQQ9PQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9NGdJDhOTgrhicDoiaj8nWV2ibeCT8W3BcZ2uCtlvH94esGkqcpDOOLnxQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9ooOLWm3orsibyz9iaX6BU2MqZDUaFYywiczIunHwpY8ZuJU6BUvja72rA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9SSssXCoSIZPskOpGzlwbZfL87ribkD26QZKQNAiauQ4WlsENJ0EbW4bA/640?wx_fmt=jpeg",
  ],
  "04-户外爆花系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEqC5EsxJO53pPaDBhEM06b3UMvjK59Rib7mHvJK9BxBo4Z8ZknDWZ9zg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErE1exRHu0oIpP7Txs0wqsSeQhfj6aUET4L3Bk2zd2GSvacQT3nFX2ibpg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEzpfPD8eOshicpX0r87iaDJnZMIUMQh5lYDsdUymibicN6ut1cVSmYjCicMA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEzaDwP4ZMW5VsRa7iaoEuA6zEVQKlHuUPSAbYuEXiaAVvms7DJ51Y6Prg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWrJnIia0hINvXeZHopoCn40f6sooKYlQjB6Y0ricKGics7bQ8KgQPHeL8WBhuy96KRddwGA0WDVnJ4Qg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEwp7GngWjNmOfH6YQD8Lib3e1icpibaKezricibrO0uHdJaibGuUgw7AL4bpA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEmDfZHYzVGxZVOvsDbW6UibT7siaCyp0q1j8AiajNF8PWOA6sJuyeuBhtg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEQicp4dIiaDJKQfJLKwalEKSPjcI48EHkicKCbbpP1gr5xfmwZoQCXUS9A/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEUbgIArib6z4ibXesO4yAzy8AaObJSW2iceekgadbHNLaM2qVpjdd2sLZA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErE14k52tan59SJZRyiclIFsKYFjpV6oYn2Q3Stbia4dEnibaBeYiaVgPyouQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTty4cnhMK8w8r6XrFOZatqnYEe6pztTMribxVGgBHbPkibwhicDXLYQLcQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTlLAsvQW8eaHKo5f042ib1j175Dh5PcFs8GDd4JiabPdGdMZmHTh1RQNg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErEoAic4DA0JMcsNEMy0FQAg6jqicvXOWy8RpYXKVLraV9OG1oILKjHWicEA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpznDtBo5cmwHfpbYMhWErETLO9XyPHHLDM5nOyEBE1nkOrBLlbavyu9HRrgQpnyVLmP1Nwtv9cmg/640?wx_fmt=jpeg",
  ],
  "05-高端氟碳系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9AoJjibEjLMMeljOGwLHibMaibHPZIFJKRoevyibia2iaHOMAiazGMIEomOtdA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZT2tVduIl94eCiciccOXH4k7rw7EWnv9Iflr8DN5rmibzdcPuFOwo4pZoBw/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTicUEDgiaPTjpg0yuXYSek6z3QvBodsTohibwAbOiaJT1zTYTNFYyia6fpBg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwJ1cpCRzx2I8kXwovuPJICstRnVlE4vfOkeANB7ibDc4E833rsn4XzAA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwDI4K4EQBZECeib578BmV6Pb9IIns8Qic8JnRk2lovIFeShdyK2q9XuHw/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwSeXHHUmLNicRcZxnx5XibZ64RDnhevPWiaLcadLic2jmIUcYALic4CGR0JA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwkngpVibTrG0gpbJy9v0iaoXLANgbv9lwcLfLvicezFAHP5ux7p23cwibUQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwF5wB6pXKmotlOYOpluuarhra0o6V8ZW5tdlgsajjVYggaDdwJpZiavQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwAtMSibR8EztslqdUH08icmTonsbZ0YEX0O1wCE3SMCfQXxEdicuiaUxecQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwPCZPkDf2yg1AXYQ2IkY3Fxmn4OsCFibIERHuQdkraXeLJQFRCvaTOmw/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwiaTlY1UogsEF8U3Y4z6fn1GYgwUmuWhuZ3YE6tE9kguwKY0SyIrVZ4A/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwuorZjQ05AwCa8m2WdNez1P6iak0UoppAH9Rqykb3aOytavNw29bnaHQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwNCRic81Xbib5O02xt75BRU3B9V4lycOwiaCGBlTEQ0Qia9kxibo8fJW5Jcg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwdZ7YvM5Fic0ibHQJSDuZdaKVRzyVZnt2AdQ6wuuCsaE1NGnLG7P8Q9BQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WweIS36QK5AmiaaQial5jI6HUwW0XXRdUiaNpy6Hkic1xkeFEG8gh6V2Vk9w/640?wx_fmt=jpeg",
  ],
  "06-户外平面系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9r5dZuVIkoViaAGtMO2BWhcIPWYmvK8DHoZeB9fMaL4lNwMPcyEBAEHg/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9TnfgUB1e8Y7F25VcW3GZSURGAEMJuh7KT5HKALPFR89Ru3JAYPfyNQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqhuicezwUtcGauERMw2rpZTWByjwFoicpQ78TxDSy3oEUVibSVAjUU6RdicicX8Bn0YjWUUjftMRR5MbQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwozX0LQ3JIU34CTbgMeGLibP4kZS4FRtwCJnEBMlib4fhfqqziawGeuXyQ/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqkwJQJNviatO6z41ww8A0WwODzvO8yAQ9cGfUvnkwC4yYRYyhAL3NaNle3pYtnAWS225gRZwg0eeA/640?wx_fmt=jpeg",
  ],
  "07-自喷修补漆": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpeF119I6HB3ZQbaLFQP4Tq9MOFOdEiaic0wSMD8icJocqeVoxic1NjcS7vDWwhry3uu5HpibHGILoFBHA/640?wx_fmt=jpeg",
  ],
  "08-户外扫金漆系列": [
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpeF119I6HB3ZQbaLFQP4TqVWk2Ty8WmnDlibYicuicrePDrDgcoL4vCEtTc10qqRUzBJ6OWoZYBKomA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWqgT7DkCpfrU3yFgdW83VG9qXG37FkVjQJXDPrJtiaKdjVubR9O1kM1oLsiaBz4QcULNvJMiajrIqfGA/640?wx_fmt=jpeg",
    "https://mmbiz.qpic.cn/mmbiz_jpg/VyHRzJfhNWpeF119I6HB3ZQbaLFQP4TqWSic01bSQYfpibia91kyfa6P9aXdadFLXUvUcvKnjkibdCKU7w6dmybt6Q/640?wx_fmt=jpeg",
  ],
};

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https
      .get(
        url,
        {
          headers: {
            "User-Agent":
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            Referer: "https://mp.weixin.qq.com/",
          },
        },
        (res) => {
          res.pipe(file);
          file.on("finish", () => {
            file.close();
            const size = fs.statSync(dest).size;
            resolve(size);
          });
        }
      )
      .on("error", (err) => {
        fs.unlink(dest, () => {});
        reject(err);
      });
  });
}

async function main() {
  let total = 0;
  let success = 0;

  for (const [series, urls] of Object.entries(SERIES)) {
    const dir = path.join(BASE_DIR, series);
    fs.mkdirSync(dir, { recursive: true });

    for (let i = 0; i < urls.length; i++) {
      const filename = `${String(i + 1).padStart(2, "0")}.jpg`;
      const dest = path.join(dir, filename);
      total++;

      try {
        const size = await download(urls[i], dest);
        console.log(`[OK] ${series}/${filename} (${(size / 1024).toFixed(1)} KB)`);
        success++;
      } catch (err) {
        console.log(`[FAIL] ${series}/${filename}: ${err.message}`);
      }

      // Small delay to be polite to the server
      await new Promise((r) => setTimeout(r, 300));
    }
  }

  console.log(`\nDone: ${success}/${total} images downloaded to ${BASE_DIR}`);
}

main().catch(console.error);
